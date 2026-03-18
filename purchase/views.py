"""
Purchase Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Q, Sum
from django.utils import timezone
from decimal import Decimal

from decorators.decorators import group_required
from .models import Supplier, Purchase, PurchaseItem
from .forms import SupplierForm, PurchaseForm, PurchaseItemFormSet
from stocks.models import Product
from stocks.services import StockManagementService


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager', 'General Manager'])
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
@group_required(['Admin', 'Manager', 'Stock Manager'])
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
@group_required(['Admin', 'Manager', 'Stock Manager'])
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
@group_required(['Admin', 'Manager'])
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
@group_required(['Admin', 'Manager', 'Stock Manager', 'General Manager'])
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
@group_required(['Admin', 'Manager', 'Stock Manager'])
def purchase_create(request):
    """Create a new purchase order."""
    if request.method == 'POST':
        form = PurchaseForm(request.POST)
        if form.is_valid():
            purchase = form.save(commit=False)
            purchase.created_by = request.user
            # Generate order number
            today = timezone.now().strftime('%Y%m%d')
            count = Purchase.objects.filter(
                order_number__startswith=f'OC-{today}'
            ).count() + 1
            purchase.order_number = f'OC-{today}-{count:04d}'
            purchase.save()
            messages.success(request, 'Orden de compra creada exitosamente.')
            return redirect('purchase:purchase_edit', pk=purchase.pk)
    else:
        form = PurchaseForm()
    
    context = {'form': form, 'title': 'Nueva Orden de Compra'}
    return render(request, 'purchase/purchase_form.html', context)


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def purchase_edit(request, pk):
    """Edit a purchase order."""
    purchase = get_object_or_404(Purchase, pk=pk)
    
    if request.method == 'POST':
        form = PurchaseForm(request.POST, instance=purchase)
        formset = PurchaseItemFormSet(request.POST, instance=purchase)
        
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            
            # Recalculate totals
            purchase.subtotal = sum(
                item.subtotal for item in purchase.items.all()
            )
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
@group_required(['Admin', 'Manager', 'Stock Manager'])
def purchase_receive(request, pk):
    """Receive a purchase order and update stock."""
    purchase = get_object_or_404(Purchase, pk=pk)
    
    if purchase.status == 'received':
        messages.warning(request, 'Esta orden ya fue recibida.')
        return redirect('purchase:purchase_list')
    
    if request.method == 'POST':
        
        for item in purchase.items.all():
            # Update stock
            StockManagementService.add_stock(
                product=item.product,
                quantity=item.quantity,
                cost=item.unit_cost,
                user=request.user,
                notes=f'Recepción de compra {purchase.order_number}',
                reference=purchase.order_number
            )
            
            # Update received quantity
            item.received_quantity = item.quantity
            item.save()
            
            # Update product cost
            item.product.cost_price = item.unit_cost
            item.product.save()
        
        # Update purchase status
        purchase.status = 'received'
        purchase.received_date = timezone.now().date()
        purchase.save()
        
        messages.success(request, 'Compra recibida y stock actualizado.')
        return redirect('purchase:purchase_list')
    
    context = {'purchase': purchase}
    return render(request, 'purchase/purchase_receive.html', context)


@login_required
@group_required(['Admin', 'Manager'])
def purchase_cancel(request, pk):
    """Cancel a purchase order."""
    purchase = get_object_or_404(Purchase, pk=pk)
    
    if purchase.status == 'received':
        messages.error(request, 'No se puede cancelar una orden ya recibida.')
        return redirect('purchase:purchase_list')
    
    if request.method == 'POST':
        purchase.status = 'cancelled'
        purchase.save()
        messages.success(request, 'Orden de compra cancelada.')
        return redirect('purchase:purchase_list')
    
    context = {'purchase': purchase}
    return render(request, 'purchase/purchase_cancel.html', context)


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
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
@group_required(['Admin', 'Manager', 'Stock Manager'])
def api_search_products(request):
    """API to search products for purchase form."""
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'results': []})
    
    products = Product.objects.filter(
        Q(name__icontains=query) |
        Q(barcode__icontains=query) |
        Q(sku__icontains=query),
        is_active=True
    )[:20]
    
    results = [{
        'id': p.id,
        'name': p.name,
        'barcode': p.barcode or '',
        'cost_price': str(p.cost_price),
    } for p in products]
    
    return JsonResponse({'results': results})
