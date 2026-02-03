"""
Stock Management Services
"""
from decimal import Decimal
from django.db import transaction
from .models import Product, StockMovement


class StockManagementService:
    """Service for managing product stock."""
    
    @staticmethod
    @transaction.atomic
    def add_stock(product, quantity, cost=None, reference='', reference_id=None, notes='', user=None):
        """
        Add stock to a product.
        
        Args:
            product: Product instance
            quantity: Quantity to add (positive)
            cost: Unit cost (optional)
            reference: Reference string
            reference_id: Reference ID
            notes: Additional notes
            user: User performing the action
        
        Returns:
            StockMovement instance
        """
        quantity = Decimal(str(quantity))
        cost = Decimal(str(cost)) if cost else product.cost_price
        
        stock_before = product.current_stock
        stock_after = stock_before + quantity
        
        # Update product stock
        product.current_stock = stock_after
        
        # Update average cost if cost provided
        if cost and cost > 0:
            total_value = (product.cost_price * stock_before) + (cost * quantity)
            if stock_after > 0:
                product.cost_price = total_value / stock_after
        
        product.save()
        
        # Create movement record
        movement = StockMovement.objects.create(
            product=product,
            movement_type='purchase',
            quantity=quantity,
            unit_cost=cost,
            stock_before=stock_before,
            stock_after=stock_after,
            reference=reference,
            reference_id=reference_id,
            notes=notes,
            created_by=user
        )
        
        return movement
    
    @staticmethod
    @transaction.atomic
    def deduct_stock(product, quantity, reference='', reference_id=None, notes='', user=None):
        """
        Deduct stock from a product (for sales).
        
        Args:
            product: Product instance
            quantity: Quantity to deduct (positive)
            reference: Reference string
            reference_id: Reference ID
            notes: Additional notes
            user: User performing the action
        
        Returns:
            tuple (success: bool, message: str, movement: StockMovement or None)
        """
        quantity = Decimal(str(quantity))
        stock_before = product.current_stock
        stock_after = stock_before - quantity
        
        # Allow negative stock with warning
        if stock_after < 0:
            notes += ' [ALERTA: Stock negativo]'
        
        # Update product stock
        product.current_stock = stock_after
        product.save()
        
        # Create movement record
        movement = StockMovement.objects.create(
            product=product,
            movement_type='sale',
            quantity=-quantity,  # Negative for deductions
            unit_cost=product.cost_price,
            stock_before=stock_before,
            stock_after=stock_after,
            reference=reference,
            reference_id=reference_id,
            notes=notes,
            created_by=user
        )
        
        return True, 'Stock deducido correctamente', movement
    
    @staticmethod
    @transaction.atomic
    def adjust_stock(product, new_quantity, reason, user=None):
        """
        Adjust stock to a specific quantity.
        
        Args:
            product: Product instance
            new_quantity: New stock quantity
            reason: Reason for adjustment
            user: User performing the action
        
        Returns:
            StockMovement instance
        """
        new_quantity = Decimal(str(new_quantity))
        stock_before = product.current_stock
        difference = new_quantity - stock_before
        
        movement_type = 'adjustment_in' if difference >= 0 else 'adjustment_out'
        
        # Update product stock
        product.current_stock = new_quantity
        product.save()
        
        # Create movement record
        movement = StockMovement.objects.create(
            product=product,
            movement_type=movement_type,
            quantity=difference,
            unit_cost=product.cost_price,
            stock_before=stock_before,
            stock_after=new_quantity,
            reference='Ajuste de inventario',
            notes=reason,
            created_by=user
        )
        
        return movement
    
    @staticmethod
    def get_stock_value(cost_price=True):
        """
        Calculate total inventory value.
        
        Args:
            cost_price: If True, use cost price; otherwise use sale price
        
        Returns:
            Decimal total value
        """
        from django.db.models import Sum, F
        
        price_field = 'cost_price' if cost_price else 'sale_price'
        
        result = Product.objects.filter(
            is_active=True,
            current_stock__gt=0
        ).aggregate(
            total=Sum(F('current_stock') * F(price_field))
        )
        
        return result['total'] or Decimal('0.00')
    
    @staticmethod
    def get_low_stock_products(min_threshold=None):
        """
        Get products with low stock.
        
        Args:
            min_threshold: Override product's min_stock
        
        Returns:
            QuerySet of products
        """
        from django.db.models import F
        
        queryset = Product.objects.filter(is_active=True)
        
        if min_threshold is not None:
            queryset = queryset.filter(current_stock__lte=min_threshold)
        else:
            queryset = queryset.filter(current_stock__lte=F('min_stock'))
        
        return queryset.select_related('category', 'unit_of_measure')
    
    @staticmethod
    def get_kardex(product, start_date=None, end_date=None):
        """
        Get stock movement history for a product.
        
        Args:
            product: Product instance
            start_date: Start date filter
            end_date: End date filter
        
        Returns:
            QuerySet of movements
        """
        queryset = StockMovement.objects.filter(product=product)
        
        if start_date:
            queryset = queryset.filter(created_at__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__lte=end_date)
        
        return queryset.order_by('created_at')


class BarcodeService:
    """Service for barcode operations."""
    
    @staticmethod
    def generate_ean13():
        """
        Generate a valid EAN-13 barcode.
        
        Returns:
            str: 13-digit EAN barcode
        """
        import random
        
        # Generate 12 random digits
        digits = [random.randint(0, 9) for _ in range(12)]
        
        # Calculate checksum (13th digit)
        odd_sum = sum(digits[::2])
        even_sum = sum(digits[1::2])
        checksum = (10 - ((odd_sum + even_sum * 3) % 10)) % 10
        
        digits.append(checksum)
        return ''.join(map(str, digits))
    
    @staticmethod
    def validate_barcode(code):
        """
        Validate a barcode checksum.
        
        Args:
            code: Barcode string
        
        Returns:
            bool: True if valid
        """
        if not code or not code.isdigit():
            return False
        
        if len(code) == 13:  # EAN-13
            digits = [int(d) for d in code]
            odd_sum = sum(digits[::2][:-1])
            even_sum = sum(digits[1::2])
            checksum = (10 - ((odd_sum + even_sum * 3) % 10)) % 10
            return checksum == digits[-1]
        elif len(code) == 12:  # UPC-A
            digits = [int(d) for d in code]
            odd_sum = sum(digits[::2][:-1])
            even_sum = sum(digits[1::2])
            checksum = (10 - ((odd_sum * 3 + even_sum) % 10)) % 10
            return checksum == digits[-1]
        elif len(code) == 8:  # EAN-8
            digits = [int(d) for d in code]
            weighted_sum = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:-1]))
            checksum = (10 - (weighted_sum % 10)) % 10
            return checksum == digits[-1]
        
        # For other lengths, just check it's numeric
        return True
    
    @staticmethod
    def search_by_barcode(code):
        """
        Search product by barcode.
        
        Args:
            code: Barcode string
        
        Returns:
            Product instance or None
        """
        from .models import Product, ProductPresentation
        
        # First try product barcode
        product = Product.objects.filter(barcode=code, is_active=True).first()
        if product:
            return product
        
        # Then try presentation barcode
        presentation = ProductPresentation.objects.filter(
            barcode=code,
            is_active=True
        ).select_related('product').first()
        
        if presentation:
            return presentation.product
        
        return None
