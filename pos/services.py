"""
POS Services - Business Logic
"""
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from datetime import datetime

from .models import POSSession, POSTransaction, POSTransactionItem, POSPayment


class POSService:
    """Service for POS operations."""
    
    @staticmethod
    def get_or_create_session(shift):
        """Get or create a POS session for a cash shift."""
        session = POSSession.objects.filter(
            cash_shift=shift,
            status='active'
        ).first()
        
        if not session:
            session = POSSession.objects.create(
                cash_shift=shift
            )
        
        return session
    
    @staticmethod
    def create_transaction(session):
        """Create a new POS transaction."""
        ticket_number = POSService.generate_ticket_number(session)
        
        transaction = POSTransaction.objects.create(
            session=session,
            ticket_number=ticket_number
        )
        
        return transaction
    
    @staticmethod
    def get_pending_transaction(session):
        """Get or create a pending transaction for a session."""
        transaction = POSTransaction.objects.filter(
            session=session,
            status='pending'
        ).first()
        
        if not transaction:
            transaction = POSService.create_transaction(session)
        
        return transaction
    
    @staticmethod
    def generate_ticket_number(session):
        """Generate a unique ticket number."""
        import random
        import string
        from django.db import IntegrityError
        
        register_code = session.cash_shift.cash_register.code or 'CAJA'
        date_str = timezone.now().strftime('%Y%m%d')
        
        # Count today's transactions for this register
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        count = POSTransaction.objects.filter(
            session__cash_shift__cash_register=session.cash_shift.cash_register,
            created_at__gte=today_start
        ).count() + 1
        
        # Generate base ticket number
        ticket_number = f'{register_code}-{date_str}-{count:04d}'
        
        # Check if it already exists and add suffix if needed
        while POSTransaction.objects.filter(ticket_number=ticket_number).exists():
            count += 1
            ticket_number = f'{register_code}-{date_str}-{count:04d}'
        
        return ticket_number


class CartService:
    """Service for cart operations."""
    
    @staticmethod
    @transaction.atomic
    def add_item(pos_transaction, product_id, quantity=Decimal('1')):
        """
        Add a product to the cart.
        
        Returns:
            tuple (item: POSTransactionItem or None, message: str)
        """
        from stocks.models import Product
        
        try:
            product = Product.objects.get(id=product_id, is_active=True)
        except Product.DoesNotExist:
            return None, 'Producto no encontrado'
        
        quantity = Decimal(str(quantity))
        
        # Check if item already exists in cart
        existing_item = POSTransactionItem.objects.filter(
            transaction=pos_transaction,
            product=product
        ).first()
        
        if existing_item:
            existing_item.quantity += quantity
            existing_item.save()
            item = existing_item
            message = f'{product.name} actualizado ({existing_item.quantity})'
        else:
            item = POSTransactionItem.objects.create(
                transaction=pos_transaction,
                product=product,
                quantity=quantity,
                unit_price=product.sale_price
            )
            message = f'{product.name} agregado'
        
        # Apply promotions
        CartService.apply_promotions(pos_transaction)
        
        # Recalculate totals
        pos_transaction.calculate_totals()
        
        return item, message
    
    @staticmethod
    @transaction.atomic
    def update_quantity(item_id, quantity):
        """Update item quantity."""
        try:
            item = POSTransactionItem.objects.get(id=item_id)
        except POSTransactionItem.DoesNotExist:
            return False, 'Ítem no encontrado'
        
        quantity = Decimal(str(quantity))
        
        if quantity <= 0:
            return CartService.remove_item(item_id)
        
        item.quantity = quantity
        item.save()
        
        # Apply promotions and recalculate
        CartService.apply_promotions(item.transaction)
        item.transaction.calculate_totals()
        
        return True, 'Cantidad actualizada'
    
    @staticmethod
    @transaction.atomic
    def remove_item(item_id):
        """Remove item from cart."""
        try:
            item = POSTransactionItem.objects.get(id=item_id)
            pos_transaction = item.transaction
            item.delete()
            
            # Apply promotions and recalculate
            CartService.apply_promotions(pos_transaction)
            pos_transaction.calculate_totals()
            
            return True, 'Ítem eliminado'
        except POSTransactionItem.DoesNotExist:
            return False, 'Ítem no encontrado'
    
    @staticmethod
    @transaction.atomic
    def clear_cart(pos_transaction):
        """Clear all items from cart."""
        pos_transaction.items.all().delete()
        pos_transaction.subtotal = Decimal('0.00')
        pos_transaction.discount_total = Decimal('0.00')
        pos_transaction.total = Decimal('0.00')
        pos_transaction.items_count = 0
        pos_transaction.save()
        
        return True, 'Carrito vaciado'
    
    @staticmethod
    def apply_promotions(pos_transaction):
        """Apply promotions to cart items."""
        from promotions.engine import PromotionEngine
        
        items = pos_transaction.items.all()
        if not items:
            return
        
        # Reset discounts
        for item in items:
            item.discount = Decimal('0.00')
            item.promotion = None
            item.promotion_name = ''
            item.save()
        
        # Get cart items data
        cart_items = [
            {
                'item_id': item.id,
                'product_id': item.product_id,
                'quantity': float(item.quantity),
                'unit_price': float(item.unit_price)
            }
            for item in items
        ]
        
        # Calculate promotions
        result = PromotionEngine.calculate_cart(cart_items)
        
        # Apply discounts to items
        for applied in result.get('applied_promotions', []):
            for item_discount in applied.get('item_discounts', []):
                item_id = item_discount.get('item_id')
                discount = Decimal(str(item_discount.get('discount', 0)))
                
                if item_id and discount > 0:
                    try:
                        item = POSTransactionItem.objects.get(id=item_id)
                        item.discount = discount
                        item.promotion_id = applied.get('promotion_id')
                        item.promotion_name = applied.get('promotion_name', '')
                        item.save()
                    except POSTransactionItem.DoesNotExist:
                        pass


class CheckoutService:
    """Service for checkout operations."""
    
    @staticmethod
    @transaction.atomic
    def process_payment(transaction_id, payments):
        """
        Process payment for a transaction.
        
        Args:
            transaction_id: POSTransaction ID
            payments: List of dicts with 'method_code' and 'amount'
        
        Returns:
            tuple (success: bool, result: dict)
        """
        from cashregister.models import PaymentMethod, CashMovement
        from stocks.services import StockManagementService
        
        try:
            pos_transaction = POSTransaction.objects.get(
                id=transaction_id,
                status='pending'
            )
        except POSTransaction.DoesNotExist:
            return False, {'error': 'Transacción no encontrada o ya procesada'}
        
        # Calculate total to pay
        total_to_pay = pos_transaction.total
        total_paid = Decimal('0.00')
        
        # Validate and create payments
        for payment_data in payments:
            method_id = payment_data.get('method_id')
            method_code = payment_data.get('method_code')
            amount = Decimal(str(payment_data.get('amount', 0)))
            
            if amount <= 0:
                continue
            
            try:
                # Support both method_id and method_code
                if method_id:
                    method = PaymentMethod.objects.get(id=method_id, is_active=True)
                elif method_code:
                    method = PaymentMethod.objects.get(code=method_code, is_active=True)
                else:
                    return False, {'error': 'Método de pago no especificado'}
            except PaymentMethod.DoesNotExist:
                return False, {'error': f'Método de pago inválido'}
            
            POSPayment.objects.create(
                transaction=pos_transaction,
                payment_method=method,
                amount=amount,
                reference=payment_data.get('reference', '')
            )
            
            # Calculate remaining amount to pay (before this payment)
            remaining = max(Decimal('0.00'), total_to_pay - total_paid)
            
            # Register cash movement only for the actual sale amount, not change
            movement_amount = min(amount, remaining) if remaining > 0 else Decimal('0.00')
            
            if movement_amount > 0:
                CashMovement.objects.create(
                    cash_shift=pos_transaction.session.cash_shift,
                    movement_type='income',
                    amount=movement_amount,
                    payment_method=method,
                    description=f'Venta {pos_transaction.ticket_number}',
                    reference=pos_transaction.ticket_number
                )
            
            total_paid += amount
        
        # Verify sufficient payment
        if total_paid < total_to_pay:
            # Rollback payments
            POSPayment.objects.filter(transaction=pos_transaction).delete()
            return False, {'error': f'Pago insuficiente. Faltan ${total_to_pay - total_paid}'}
        
        # Calculate change
        change = total_paid - total_to_pay
        
        # Deduct stock
        for item in pos_transaction.items.all():
            StockManagementService.deduct_stock(
                product=item.product,
                quantity=item.quantity,
                reference=f'Venta {pos_transaction.ticket_number}',
                reference_id=pos_transaction.id
            )
        
        # Complete transaction
        pos_transaction.status = 'completed'
        pos_transaction.completed_at = timezone.now()
        pos_transaction.amount_paid = total_paid
        pos_transaction.change_given = change
        pos_transaction.save()
        
        return True, {
            'success': True,
            'transaction_id': pos_transaction.id,
            'ticket_number': pos_transaction.ticket_number,
            'total': float(total_to_pay),
            'paid': float(total_paid),
            'change': float(change),
            'items_count': pos_transaction.items_count
        }
    
    @staticmethod
    @transaction.atomic
    def cancel_transaction(transaction_id, reason=''):
        """Cancel a transaction."""
        try:
            pos_transaction = POSTransaction.objects.get(
                id=transaction_id,
                status='pending'
            )
        except POSTransaction.DoesNotExist:
            return False, 'Transacción no encontrada'
        
        pos_transaction.status = 'cancelled'
        pos_transaction.cancelled_at = timezone.now()
        pos_transaction.notes = reason
        pos_transaction.save()
        
        return True, 'Transacción cancelada'
    
    @staticmethod
    @transaction.atomic
    def suspend_transaction(transaction_id):
        """Suspend a transaction for later."""
        try:
            pos_transaction = POSTransaction.objects.get(
                id=transaction_id,
                status='pending'
            )
        except POSTransaction.DoesNotExist:
            return False, 'Transacción no encontrada'
        
        pos_transaction.status = 'suspended'
        pos_transaction.suspended_at = timezone.now()
        pos_transaction.save()
        
        return True, 'Transacción suspendida'
    
    @staticmethod
    @transaction.atomic
    def resume_transaction(transaction_id):
        """Resume a suspended transaction."""
        try:
            pos_transaction = POSTransaction.objects.get(
                id=transaction_id,
                status='suspended'
            )
        except POSTransaction.DoesNotExist:
            return False, 'Transacción no encontrada'
        
        pos_transaction.status = 'pending'
        pos_transaction.suspended_at = None
        pos_transaction.save()
        
        return True, 'Transacción reanudada'
    
    @staticmethod
    @transaction.atomic
    def process_cost_sale(transaction_id, payments, employee_note=''):
        """
        Process a sale at cost price (for employees/owners).
        
        Args:
            transaction_id: POSTransaction ID
            payments: List of dicts with 'method_code' and 'amount'
            employee_note: Optional note about who consumed
        
        Returns:
            tuple (success: bool, result: dict)
        """
        from cashregister.models import PaymentMethod, CashMovement
        from stocks.services import StockManagementService
        
        try:
            pos_transaction = POSTransaction.objects.get(
                id=transaction_id,
                status='pending'
            )
        except POSTransaction.DoesNotExist:
            return False, {'error': 'Transacción no encontrada o ya procesada'}
        
        # Update item prices to cost price and recalculate
        for item in pos_transaction.items.all():
            item.unit_price = item.product.cost_price or item.product.purchase_price
            item.discount = Decimal('0.00')  # No discounts on cost sales
            item.subtotal = item.unit_price * item.quantity
            item.save()
        
        # Recalculate totals
        pos_transaction.calculate_totals()
        pos_transaction.refresh_from_db()
        
        # Calculate total to pay (at cost)
        total_to_pay = pos_transaction.total
        total_paid = Decimal('0.00')
        
        # Validate and create payments
        for payment_data in payments:
            method_id = payment_data.get('method_id')
            method_code = payment_data.get('method_code')
            amount = Decimal(str(payment_data.get('amount', 0)))
            
            if amount <= 0:
                continue
            
            try:
                if method_id:
                    method = PaymentMethod.objects.get(id=method_id, is_active=True)
                elif method_code:
                    method = PaymentMethod.objects.get(code=method_code, is_active=True)
                else:
                    return False, {'error': 'Método de pago no especificado'}
            except PaymentMethod.DoesNotExist:
                return False, {'error': f'Método de pago inválido'}
            
            POSPayment.objects.create(
                transaction=pos_transaction,
                payment_method=method,
                amount=amount,
                reference=f'Venta al costo - {employee_note}'
            )
            
            # Calculate remaining amount to pay (before this payment)
            remaining = max(Decimal('0.00'), total_to_pay - total_paid)
            
            # Register cash movement only for the actual sale amount, not change
            movement_amount = min(amount, remaining) if remaining > 0 else Decimal('0.00')
            
            if movement_amount > 0:
                CashMovement.objects.create(
                    cash_shift=pos_transaction.session.cash_shift,
                    movement_type='income',
                    amount=movement_amount,
                    payment_method=method,
                    description=f'Venta al costo {pos_transaction.ticket_number}',
                    reference=pos_transaction.ticket_number
                )
            
            total_paid += amount
        
        # Verify sufficient payment
        if total_paid < total_to_pay:
            POSPayment.objects.filter(transaction=pos_transaction).delete()
            return False, {'error': f'Pago insuficiente. Faltan ${total_to_pay - total_paid}'}
        
        # Calculate change
        change = total_paid - total_to_pay
        
        # Deduct stock
        for item in pos_transaction.items.all():
            StockManagementService.deduct_stock(
                product=item.product,
                quantity=item.quantity,
                reference=f'Venta al costo {pos_transaction.ticket_number}',
                reference_id=pos_transaction.id
            )
        
        # Complete transaction
        pos_transaction.transaction_type = 'cost_sale'
        pos_transaction.status = 'completed'
        pos_transaction.completed_at = timezone.now()
        pos_transaction.amount_paid = total_paid
        pos_transaction.change_given = change
        pos_transaction.notes = f'VENTA AL COSTO - {employee_note}'
        pos_transaction.save()
        
        return True, {
            'success': True,
            'transaction_id': pos_transaction.id,
            'ticket_number': pos_transaction.ticket_number,
            'total': float(total_to_pay),
            'paid': float(total_paid),
            'change': float(change),
            'items_count': pos_transaction.items_count,
            'type': 'cost_sale'
        }
    
    @staticmethod
    @transaction.atomic
    def process_internal_consumption(transaction_id, consumer_note=''):
        """
        Process internal consumption (deduct from stock without payment).
        
        Args:
            transaction_id: POSTransaction ID
            consumer_note: Who/why consumed (for traceability)
        
        Returns:
            tuple (success: bool, result: dict)
        """
        from stocks.services import StockManagementService
        
        try:
            pos_transaction = POSTransaction.objects.get(
                id=transaction_id,
                status='pending'
            )
        except POSTransaction.DoesNotExist:
            return False, {'error': 'Transacción no encontrada o ya procesada'}
        
        if pos_transaction.items.count() == 0:
            return False, {'error': 'El carrito está vacío'}
        
        # Update to cost prices for record keeping
        total_cost = Decimal('0.00')
        for item in pos_transaction.items.all():
            cost = item.product.cost_price or item.product.purchase_price
            item.unit_price = cost
            item.discount = Decimal('0.00')
            item.subtotal = cost * item.quantity
            item.save()
            total_cost += item.subtotal
        
        # Deduct stock
        for item in pos_transaction.items.all():
            StockManagementService.deduct_stock(
                product=item.product,
                quantity=item.quantity,
                reference=f'Consumo interno {pos_transaction.ticket_number} - {consumer_note}',
                reference_id=pos_transaction.id
            )
        
        # Complete transaction with zero payment
        pos_transaction.transaction_type = 'internal_consumption'
        pos_transaction.status = 'completed'
        pos_transaction.completed_at = timezone.now()
        pos_transaction.subtotal = total_cost
        pos_transaction.total = Decimal('0.00')  # No payment required
        pos_transaction.amount_paid = Decimal('0.00')
        pos_transaction.change_given = Decimal('0.00')
        pos_transaction.notes = f'CONSUMO INTERNO - {consumer_note}'
        pos_transaction.save()
        
        return True, {
            'success': True,
            'transaction_id': pos_transaction.id,
            'ticket_number': pos_transaction.ticket_number,
            'cost_value': float(total_cost),  # Value at cost for reference
            'items_count': pos_transaction.items_count,
            'type': 'internal_consumption'
        }
