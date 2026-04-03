"""
Purchase Views
"""
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum
from django.db import transaction
from django.utils import timezone
from decimal import Decimal

from decorators.decorators import group_required
from .models import Supplier, Purchase, PurchaseItem
from .forms import SupplierForm, PurchaseForm, PurchaseItemFormSet
from stocks.models import Product, StockBatch
from stocks.services import StockManagementService


@login_required
@group_required(['Admin'])
def supplier_list(request):
    """List all suppliers."""
    suppliers = Supplier.objects.filter(is_active=True)
    
    search = request.GET.get('search', '')
    if search:
        suppliers = suppliers.filter(
            Q(name__icontains=search) |
            Q(contact_name__icontains=search) |
            Q(cuit__icontains=search)
        )
    
    context = {
        'suppliers': suppliers,
        'search': search,
    }
    return render(request, 'purchase/supplier_list.html', context)


@login_required
@group_required(['Admin'])
def supplier_create(request):
    """Create a new supplier."""
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor creado exitosamente.')
            return redirect('purchase:supplier_list')
    else:
        form = SupplierForm()
    
    context = {'form': form, 'title': 'Nuevo Proveedor'}
    return render(request, 'purchase/supplier_form.html', context)


@login_required
@group_required(['Admin'])
def supplier_edit(request, pk):
    """Edit a supplier."""
    supplier = get_object_or_404(Supplier, pk=pk)
    
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            messages.success(request, 'Proveedor actualizado exitosamente.')
            return redirect('purchase:supplier_list')
    else:
        form = SupplierForm(instance=supplier)
    
    context = {
        'form': form,
        'supplier': supplier,
        'title': f'Editar {supplier.name}'
    }
    return render(request, 'purchase/supplier_form.html', context)


@login_required
@group_required(['Admin'])
def supplier_delete(request, pk):
    """Delete a supplier."""
    supplier = get_object_or_404(Supplier, pk=pk)
    
    if request.method == 'POST':
        supplier.is_active = False
        supplier.save()
        messages.success(request, 'Proveedor eliminado exitosamente.')
        return redirect('purchase:supplier_list')
    
    context = {'supplier': supplier}
    return render(request, 'purchase/supplier_confirm_delete.html', context)


@login_required
@group_required(['Admin'])
def purchase_list(request):
    """List all purchases."""
    purchases = Purchase.objects.select_related('supplier', 'created_by').all()

    status = request.GET.get('status', '')
    if status:
        purchases = purchases.filter(status=status)

    supplier_id = request.GET.get('supplier', '')
    if supplier_id:
        purchases = purchases.filter(supplier_id=supplier_id)

    date_from = request.GET.get('date_from', '')
    if date_from:
        purchases = purchases.filter(order_date__gte=date_from)

    date_to = request.GET.get('date_to', '')
    if date_to:
        purchases = purchases.filter(order_date__lte=date_to)

    search = request.GET.get('search', '')
    if search:
        purchases = purchases.filter(
            Q(order_number__icontains=search) |
            Q(supplier__name__icontains=search)
        )

    total = purchases.aggregate(total=Sum('total'))['total'] or 0

    context = {
        'purchases': purchases,
        'status': status,
        'search': search,
        'status_choices': Purchase.STATUS_CHOICES,
        'suppliers': Supplier.objects.filter(is_active=True).order_by('name'),
        'supplier': supplier_id,
        'date_from': date_from,
        'date_to': date_to,
        'total': total,
    }
    return render(request, 'purchase/purchase_list.html', context)


@login_required
@group_required(['Admin'])
def purchase_create(request):
    """Create a new purchase order with items in one step (JSON POST)."""
    if request.method == 'POST':
        # Accept both JSON (fetch) and form POST (hidden field)
        content_type = request.content_type or ''
        if 'application/json' in content_type:
            try:
                data = json.loads(request.body)
            except (json.JSONDecodeError, AttributeError):
                return JsonResponse({'error': 'JSON inválido'}, status=400)
        else:
            raw = request.POST.get('order_data', '')
            try:
                data = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                messages.error(request, 'Error procesando el formulario.')
                return redirect('purchase:purchase_create')

        supplier_id = data.get('supplier_id')
        order_date = data.get('order_date') or None
        tax_percent = Decimal(str(data.get('tax_percent', '0')))
        notes = data.get('notes', '')
        items = data.get('items', [])

        error = None
        if not supplier_id:
            error = 'Seleccioná un proveedor.'
        elif not items:
            error = 'Agregá al menos un producto.'

        if error:
            if 'application/json' in content_type:
                return JsonResponse({'error': error}, status=400)
            messages.error(request, error)
            return redirect('purchase:purchase_create')

        try:
            with transaction.atomic():
                today = timezone.now().strftime('%Y%m%d')
                count = Purchase.objects.filter(
                    order_number__startswith=f'OC-{today}'
                ).count() + 1

                purchase = Purchase.objects.create(
                    supplier_id=supplier_id,
                    order_number=f'OC-{today}-{count:04d}',
                    order_date=order_date,
                    tax_percent=tax_percent,
                    notes=notes,
                    created_by=request.user,
                )

                subtotal = Decimal('0')
                for row in items:
                    product_id = row.get('product_id')
                    quantity = int(row.get('quantity', 0))
                    unit_cost = Decimal(str(row.get('unit_cost', '0')))
                    sale_price_val = row.get('sale_price')
                    sale_price = Decimal(str(sale_price_val)) if sale_price_val else None

                    if not product_id or quantity < 1 or unit_cost <= 0:
                        raise ValueError(f'Datos inválidos: producto={product_id} qty={quantity} cost={unit_cost}')

                    if not Product.objects.filter(pk=product_id, is_active=True).exists():
                        raise ValueError(f'Producto con id={product_id} no existe o está inactivo.')

                    item_subtotal = unit_cost * quantity
                    PurchaseItem.objects.create(
                        purchase=purchase,
                        product_id=product_id,
                        quantity=quantity,
                        unit_cost=unit_cost,
                        sale_price=sale_price,
                        subtotal=item_subtotal,
                    )
                    subtotal += item_subtotal

                tax_amount = (subtotal * tax_percent / 100).quantize(Decimal('0.01'))
                purchase.subtotal = subtotal
                purchase.tax = tax_amount
                purchase.total = subtotal + tax_amount
                purchase.save()

        except Exception as e:
            if 'application/json' in content_type:
                return JsonResponse({'error': str(e)}, status=400)
            messages.error(request, str(e))
            return redirect('purchase:purchase_create')

        if 'application/json' in content_type:
            return JsonResponse({'success': True, 'pk': purchase.pk, 'order_number': purchase.order_number})

        messages.success(request, f'Orden {purchase.order_number} creada exitosamente.')
        return redirect('purchase:purchase_list')

    # GET: render form
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    return render(request, 'purchase/purchase_form.html', {
        'suppliers': suppliers,
        'title': 'Nueva Orden de Compra',
    })


@login_required
@group_required(['Admin'])
def purchase_edit(request, pk):
    """Edit a purchase order."""
    purchase = get_object_or_404(Purchase, pk=pk)
    
    if request.method == 'POST':
        form = PurchaseForm(request.POST, instance=purchase)
        formset = PurchaseItemFormSet(request.POST, instance=purchase)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()

            # Recalculate totals using tax_percent
            purchase.refresh_from_db()
            purchase.subtotal = sum(item.subtotal for item in purchase.items.all())
            purchase.tax = (purchase.subtotal * purchase.tax_percent / 100).quantize(Decimal('0.01'))
            purchase.total = purchase.subtotal + purchase.tax
            purchase.save()
            
            messages.success(request, 'Orden de compra actualizada.')
            return redirect('purchase:purchase_list')
    else:
        form = PurchaseForm(instance=purchase)
        formset = PurchaseItemFormSet(instance=purchase)
    
    context = {
        'form': form,
        'formset': formset,
        'purchase': purchase,
        'title': f'Editar {purchase.order_number}'
    }
    return render(request, 'purchase/purchase_edit.html', context)


@login_required
@group_required(['Admin'])
def purchase_receive(request, pk):
    """Receive a purchase order and update stock."""
    purchase = get_object_or_404(Purchase, pk=pk)
    
    if purchase.status == 'received':
        messages.warning(request, 'Esta orden ya fue recibida.')
        return redirect('purchase:purchase_list')
    
    if request.method == 'POST':
        with transaction.atomic():
            for item in purchase.items.all():
                # Update stock and weighted average cost
                StockManagementService.add_stock(
                    product=item.product,
                    quantity=item.quantity,
                    cost=item.unit_cost,
                    user=request.user,
                    notes=f'Recepción de compra {purchase.order_number}',
                    reference=purchase.order_number
                )

                # Create stock batch for FIFO tracking
                from datetime import datetime
                batch_date = (
                    datetime.combine(purchase.received_date, datetime.min.time())
                    if purchase.received_date else timezone.now()
                )
                StockBatch.objects.create(
                    product=item.product,
                    purchase=purchase,
                    supplier_name=purchase.supplier.name,
                    quantity_purchased=item.quantity,
                    quantity_remaining=item.quantity,
                    purchase_price=item.unit_cost,
                    purchased_at=batch_date,
                    created_by=request.user,
                    notes=f'OC {purchase.order_number}',
                )

                # Update product sale_price if specified
                if item.sale_price:
                    item.product.sale_price = item.sale_price
                    item.product.save(update_fields=['sale_price'])

                item.received_quantity = item.quantity
                item.save()

            purchase.status = 'received'
            purchase.received_date = timezone.now().date()
            purchase.save()

        messages.success(request, 'Compra recibida, stock y lotes actualizados.')
        return redirect('purchase:purchase_list')
    
    context = {'purchase': purchase}
    return render(request, 'purchase/purchase_receive.html', context)


@login_required
@group_required(['Admin'])
def purchase_cancel(request, pk):
    """Cancel a purchase order."""
    purchase = get_object_or_404(Purchase, pk=pk)
    
    if purchase.status == 'received':
        messages.error(request, 'No se puede cancelar una orden ya recibida.')
        return redirect('purchase:purchase_list')

    if purchase.status == 'cancelled':
        messages.warning(request, 'Esta orden ya fue cancelada.')
        return redirect('purchase:purchase_list')

    if request.method == 'POST':
        purchase.status = 'cancelled'
        purchase.save()
        messages.success(request, 'Orden de compra cancelada.')
        return redirect('purchase:purchase_list')
    
    context = {'purchase': purchase}
    return render(request, 'purchase/purchase_cancel.html', context)


@login_required
@group_required(['Admin'])
def purchase_detail(request, pk):
    """View purchase order details."""
    purchase = get_object_or_404(Purchase, pk=pk)
    context = {
        'purchase': purchase,
        'items': purchase.items.select_related('product').all(),
    }
    return render(request, 'purchase/purchase_detail.html', context)


# API Views
@login_required
@group_required(['Admin'])
def api_search_products(request):
    """API to search products for purchase form. Supports exact barcode lookup."""
    query = request.GET.get('q', '')
    is_barcode_scan = request.GET.get('barcode') == '1'

    if len(query) < 2:
        return JsonResponse({'results': []})

    if is_barcode_scan:
        # Exact barcode match first, then fallback to contains
        products = list(Product.objects.filter(barcode=query, is_active=True)[:1])
        if not products:
            products = list(Product.objects.filter(
                Q(barcode__icontains=query) | Q(sku__icontains=query) | Q(name__icontains=query),
                is_active=True
            )[:10])
    else:
        products = list(Product.objects.filter(
            Q(name__icontains=query) |
            Q(barcode__icontains=query) |
            Q(sku__icontains=query),
            is_active=True
        )[:20])

    results = [{
        'id': p.id,
        'name': p.name,
        'barcode': p.barcode or '',
        'cost_price': str(p.cost_price),
        'sale_price': str(p.sale_price),
    } for p in products]

    return JsonResponse({'results': results})
