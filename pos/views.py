"""
POS Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.db.models import Q
from decimal import Decimal
import json
import unicodedata

from .models import POSSession, POSTransaction, POSTransactionItem, POSPayment, QuickAccessButton


def normalize_text(text):
    """Remove accents and convert to lowercase for search."""
    if not text:
        return ''
    # Normalize to NFD form (separates characters and diacritics)
    nfkd_form = unicodedata.normalize('NFKD', text)
    # Remove diacritical marks
    return ''.join(c for c in nfkd_form if not unicodedata.combining(c)).lower()
from .services import POSService, CartService, CheckoutService
from cashregister.models import CashShift, PaymentMethod
from stocks.models import Product
from company.models import Company
from decorators.decorators import group_required


@login_required
@group_required(['Admin', 'Manager', 'Cashier', 'General Manager'])
def pos_main(request):
    """Main POS view."""
    # Check if user has an open shift
    shift = CashShift.objects.filter(
        cashier=request.user,
        status='open'
    ).first()
    
    if not shift:
        messages.warning(request, 'Debes abrir un turno de caja para usar el POS.')
        return redirect('cashregister:open_shift')
    
    # Get or create POS session
    session = POSService.get_or_create_session(shift)
    
    # Get or create pending transaction
    transaction = POSService.get_pending_transaction(session)
    
    # If transaction is completed, create a new one
    if transaction.status == 'completed':
        transaction = POSService.create_transaction(session)
    
    # Get cart items
    items = transaction.items.select_related('product', 'promotion').all()
    
    # Get quick access buttons
    quick_buttons = QuickAccessButton.objects.filter(
        is_active=True,
        product__is_active=True
    ).select_related('product').order_by('position')
    
    # Get products marked for quick access
    quick_access_products = Product.objects.filter(
        is_active=True,
        is_quick_access=True
    ).order_by('quick_access_position')
    
    # Get payment methods
    payment_methods = PaymentMethod.objects.filter(is_active=True).order_by('position')
    
    context = {
        'shift': shift,
        'cash_register': shift.cash_register,
        'session': session,
        'transaction': transaction,
        'items': items,
        'quick_buttons': quick_buttons,
        'quick_access_products': quick_access_products,
        'payment_methods': payment_methods,
    }
    
    return render(request, 'pos/pos_main.html', context)


# API Endpoints

@login_required
@require_GET
def api_search(request):
    """Search products with accent-insensitive matching."""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'products': []})
    
    # Normalize query (remove accents)
    query_normalized = normalize_text(query)
    
    # Check if it's a barcode (8-13 digits)
    if query.isdigit() and 8 <= len(query) <= 13:
        products = Product.objects.filter(is_active=True, barcode=query)
    elif len(query) >= 1:
        # Get all active products and filter in Python for accent-insensitive search
        all_products = Product.objects.filter(is_active=True).select_related('unit_of_measure', 'category')
        
        # Filter products where normalized name/sku/barcode contains normalized query
        matching_ids = []
        for p in all_products:
            name_normalized = normalize_text(p.name)
            sku_normalized = normalize_text(p.sku) if p.sku else ''
            barcode = p.barcode or ''
            
            if (query_normalized in name_normalized or 
                query_normalized in sku_normalized or
                query in barcode):
                matching_ids.append(p.id)
        
        products = Product.objects.filter(id__in=matching_ids).select_related('unit_of_measure', 'category').order_by('name')[:15]
    else:
        products = Product.objects.none()
    
    data = {
        'products': [
            {
                'id': p.id,
                'name': p.name,
                'barcode': p.barcode or '',
                'sku': p.sku,
                'unit_price': float(p.sale_price),
                'stock': float(p.current_stock),
                'unit': p.get_unit_display(),
                'is_bulk': p.is_bulk,
                'bulk_unit': p.bulk_unit if p.is_bulk else None,
                'allow_sell_by_amount': p.allow_sell_by_amount,
                'has_parent': p.parent_product is not None,
                'parent_name': p.parent_product.name if p.parent_product else None,
            }
            for p in products
        ]
    }
    
    return JsonResponse(data)


@login_required
@require_GET
def api_calculate_cost_total(request, transaction_id):
    """Calculate total at cost price for a transaction."""
    from decimal import Decimal
    
    try:
        transaction = POSTransaction.objects.get(id=transaction_id, status='pending')
    except POSTransaction.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transacción no encontrada'}, status=404)
    
    total_cost = Decimal('0.00')
    items_cost = []
    
    for item in transaction.items.select_related('product').all():
        cost_price = item.product.cost_price or item.product.purchase_price or Decimal('0.00')
        item_cost = cost_price * item.quantity
        total_cost += item_cost
        items_cost.append({
            'product_name': item.product.name,
            'quantity': float(item.quantity),
            'cost_price': float(cost_price),
            'total': float(item_cost)
        })
    
    return JsonResponse({
        'success': True,
        'total_cost': float(total_cost),
        'items': items_cost
    })


@login_required
@require_POST
def api_cart_add(request):
    """Add item to cart."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    
    transaction_id = data.get('transaction_id')
    product_id = data.get('product_id')
    quantity = data.get('quantity', 1)
    
    if not transaction_id or not product_id:
        return JsonResponse({'success': False, 'error': 'Datos incompletos'}, status=400)
    
    try:
        transaction = POSTransaction.objects.get(id=transaction_id, status='pending')
    except POSTransaction.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transacción no encontrada'}, status=404)
    
    item, message = CartService.add_item(transaction, product_id, Decimal(str(quantity)))
    
    if item:
        return JsonResponse({
            'success': True,
            'item_id': item.id,
            'message': message,
            'totals': {
                'subtotal': float(transaction.subtotal),
                'discount': float(transaction.discount_total),
                'total': float(transaction.total),
                'items_count': transaction.items_count
            }
        })
    
    return JsonResponse({'success': False, 'error': message}, status=400)


@login_required
@require_POST
def api_cart_update(request, item_id):
    """Update cart item quantity."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    
    quantity = data.get('quantity')
    
    if quantity is None:
        return JsonResponse({'success': False, 'error': 'Cantidad no especificada'}, status=400)
    
    success, message = CartService.update_quantity(item_id, quantity)
    
    if success:
        item = POSTransactionItem.objects.get(id=item_id)
        transaction = item.transaction
        return JsonResponse({
            'success': True,
            'message': message,
            'totals': {
                'subtotal': float(transaction.subtotal),
                'discount': float(transaction.discount_total),
                'total': float(transaction.total),
                'items_count': transaction.items_count
            }
        })
    
    return JsonResponse({'success': False, 'error': message}, status=400)


@login_required
@require_POST
def api_cart_remove(request, item_id):
    """Remove item from cart."""
    success, message = CartService.remove_item(item_id)
    
    if success:
        return JsonResponse({'success': True, 'message': message})
    
    return JsonResponse({'success': False, 'error': message}, status=400)


@login_required
@require_POST
def api_calculate_by_amount(request):
    """
    Calculate quantity based on amount for bulk products.
    e.g.: "$500 de gomitas" returns the quantity in kg/gr
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    
    product_id = data.get('product_id')
    amount = data.get('amount')
    
    if not product_id or amount is None:
        return JsonResponse({'success': False, 'error': 'Datos incompletos'}, status=400)
    
    try:
        product = Product.objects.get(id=product_id, is_active=True)
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Producto no encontrado'}, status=404)
    
    if not product.allow_sell_by_amount:
        return JsonResponse({
            'success': False, 
            'error': 'Este producto no permite venta por monto'
        }, status=400)
    
    quantity, actual_total = product.calculate_quantity_for_amount(Decimal(str(amount)))
    
    return JsonResponse({
        'success': True,
        'product_id': product.id,
        'product_name': product.name,
        'requested_amount': float(amount),
        'quantity': float(quantity),
        'unit': product.get_unit_display(),
        'unit_price': float(product.sale_price),
        'actual_total': float(actual_total),
        'is_bulk': product.is_bulk,
    })


@login_required
@require_POST
def api_cart_add_by_amount(request):
    """
    Add item to cart by specifying the amount instead of quantity.
    Calculates the quantity based on the price.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    
    transaction_id = data.get('transaction_id')
    product_id = data.get('product_id')
    amount = data.get('amount')
    
    if not transaction_id or not product_id or amount is None:
        return JsonResponse({'success': False, 'error': 'Datos incompletos'}, status=400)
    
    try:
        transaction = POSTransaction.objects.get(id=transaction_id, status='pending')
        product = Product.objects.get(id=product_id, is_active=True)
    except POSTransaction.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transacción no encontrada'}, status=404)
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Producto no encontrado'}, status=404)
    
    if not product.allow_sell_by_amount:
        return JsonResponse({
            'success': False, 
            'error': 'Este producto no permite venta por monto'
        }, status=400)
    
    # Calculate quantity from amount
    quantity, actual_total = product.calculate_quantity_for_amount(Decimal(str(amount)))
    
    if quantity <= 0:
        return JsonResponse({'success': False, 'error': 'Cantidad inválida'}, status=400)
    
    # Add to cart
    item, message = CartService.add_item(transaction, product_id, quantity)
    
    if item:
        return JsonResponse({
            'success': True,
            'item_id': item.id,
            'message': f'{quantity} {product.get_unit_display()} de {product.name}',
            'quantity': float(quantity),
            'unit': product.get_unit_display(),
            'actual_total': float(actual_total),
            'totals': {
                'subtotal': float(transaction.subtotal),
                'discount': float(transaction.discount_total),
                'total': float(transaction.total),
                'items_count': transaction.items_count
            }
        })
    
    return JsonResponse({'success': False, 'error': message}, status=400)


@login_required
@require_POST
def api_cart_clear(request, transaction_id):
    """Clear cart."""
    try:
        transaction = POSTransaction.objects.get(id=transaction_id, status='pending')
    except POSTransaction.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Transacción no encontrada'}, status=404)
    
    success, message = CartService.clear_cart(transaction)
    
    return JsonResponse({'success': success, 'message': message})


@login_required
@require_GET
def api_transaction_detail(request, transaction_id):
    """Get transaction details."""
    try:
        transaction = POSTransaction.objects.get(id=transaction_id)
    except POSTransaction.DoesNotExist:
        return JsonResponse({'error': 'Transacción no encontrada'}, status=404)
    
    items = transaction.items.select_related('product', 'promotion').all()
    
    data = {
        'id': transaction.id,
        'ticket_number': transaction.ticket_number,
        'status': transaction.status,
        'items': [
            {
                'id': item.id,
                'product_id': item.product.id,
                'product_name': item.product.name,
                'quantity': float(item.quantity),
                'unit_price': float(item.unit_price),
                'discount': float(item.discount),
                'subtotal': float(item.subtotal),
                'promotion_name': item.promotion_name
            }
            for item in items
        ],
        'totals': {
            'subtotal': float(transaction.subtotal),
            'discount': float(transaction.discount_total),
            'total': float(transaction.total),
            'items_count': transaction.items_count
        }
    }
    
    return JsonResponse(data)


@login_required
@require_POST
def api_checkout(request):
    """Process checkout."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    
    transaction_id = data.get('transaction_id')
    payments = data.get('payments', [])
    
    if not transaction_id or not payments:
        return JsonResponse({'success': False, 'error': 'Datos incompletos'}, status=400)
    
    success, result = CheckoutService.process_payment(transaction_id, payments)
    
    if success:
        return JsonResponse(result)
    
    return JsonResponse({'success': False, **result}, status=400)


@login_required
@require_POST
def api_checkout_cost_sale(request):
    """Process checkout at cost price for employees/owners."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    
    transaction_id = data.get('transaction_id')
    payments = data.get('payments', [])
    employee_note = data.get('note', '')
    
    if not transaction_id or not payments:
        return JsonResponse({'success': False, 'error': 'Datos incompletos'}, status=400)
    
    success, result = CheckoutService.process_cost_sale(transaction_id, payments, employee_note)
    
    if success:
        return JsonResponse(result)
    
    return JsonResponse({'success': False, **result}, status=400)


@login_required
@require_POST
def api_checkout_internal_consumption(request):
    """Process internal consumption (stock deduction without payment)."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    
    transaction_id = data.get('transaction_id')
    consumer_note = data.get('note', request.user.get_full_name() or request.user.username)
    
    if not transaction_id:
        return JsonResponse({'success': False, 'error': 'Datos incompletos'}, status=400)
    
    success, result = CheckoutService.process_internal_consumption(transaction_id, consumer_note)
    
    if success:
        return JsonResponse(result)
    
    return JsonResponse({'success': False, **result}, status=400)


@login_required
@require_POST
def api_transaction_suspend(request, transaction_id):
    """Suspend transaction."""
    success, message = CheckoutService.suspend_transaction(transaction_id)
    
    return JsonResponse({'success': success, 'message': message})


@login_required
@require_POST
def api_transaction_resume(request, transaction_id):
    """Resume suspended transaction."""
    success, message = CheckoutService.resume_transaction(transaction_id)
    
    return JsonResponse({'success': success, 'message': message})


@login_required
@require_POST
def api_transaction_cancel(request, transaction_id):
    """Cancel transaction."""
    try:
        data = json.loads(request.body)
        reason = data.get('reason', '')
    except json.JSONDecodeError:
        reason = ''
    
    success, message = CheckoutService.cancel_transaction(transaction_id, reason)
    
    return JsonResponse({'success': success, 'message': message})


@login_required
def suspended_transactions(request):
    """View suspended transactions."""
    transactions = POSTransaction.objects.filter(
        status='suspended',
        session__cash_shift__cashier=request.user
    ).select_related('session__cash_shift__cash_register')
    
    return render(request, 'pos/suspended_transactions.html', {
        'transactions': transactions
    })


@login_required
def print_ticket(request, transaction_id):
    """Generate printable ticket for a transaction."""
    transaction = get_object_or_404(
        POSTransaction.objects.select_related(
            'session__cash_shift__cashier',
            'session__cash_shift__cash_register'
        ),
        pk=transaction_id
    )
    
    # Get items with products
    items = transaction.items.select_related('product', 'product__unit_of_measure', 'promotion').all()
    
    # Get payments
    payments = []
    payment_method_name = None
    for payment in transaction.payments.select_related('payment_method').all():
        payments.append({
            'method_name': payment.payment_method.name,
            'amount': payment.amount
        })
        if not payment_method_name:
            payment_method_name = payment.payment_method.name
    
    # Get company info
    company = Company.get_company()
    
    context = {
        'transaction': transaction,
        'items': items,
        'payments': payments,
        'payment_method_name': payment_method_name,
        'company': company,
    }
    
    return render(request, 'pos/ticket.html', context)


@login_required
@require_GET
def api_last_transaction(request):
    """Get the last completed transaction for the current user's shift."""
    shift = CashShift.objects.filter(
        cashier=request.user,
        status='open'
    ).first()
    
    if not shift:
        return JsonResponse({'success': False, 'error': 'No hay turno abierto'}, status=400)
    
    transaction = POSTransaction.objects.filter(
        session__cash_shift=shift,
        status='completed'
    ).order_by('-completed_at').first()
    
    if not transaction:
        return JsonResponse({'success': False, 'error': 'No hay transacciones completadas'}, status=404)
    
    return JsonResponse({
        'success': True,
        'transaction_id': transaction.id,
        'ticket_number': transaction.ticket_number,
        'total': float(transaction.total)
    })

