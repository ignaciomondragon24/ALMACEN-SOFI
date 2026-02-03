"""
Stocks Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, F
from django.core.paginator import Paginator

from .models import Product, ProductCategory, UnitOfMeasure, StockMovement
from .forms import ProductForm, CategoryForm, UnitForm, StockAdjustmentForm
from .services import StockManagementService, BarcodeService
from decorators.decorators import group_required


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def product_list(request):
    """List all products."""
    products = Product.objects.select_related('category', 'unit_of_measure')
    
    # Filters
    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    stock_alert = request.GET.get('stock_alert', '')
    
    if search:
        products = products.filter(
            Q(name__icontains=search) |
            Q(sku__icontains=search) |
            Q(barcode__icontains=search)
        )
    
    if category:
        products = products.filter(category_id=category)
    
    if status == 'active':
        products = products.filter(is_active=True)
    elif status == 'inactive':
        products = products.filter(is_active=False)
    
    if stock_alert == 'low':
        products = products.filter(current_stock__lte=F('min_stock'))
    elif stock_alert == 'out':
        products = products.filter(current_stock=0)
    
    # Pagination
    paginator = Paginator(products, 20)
    page = request.GET.get('page', 1)
    products = paginator.get_page(page)
    
    categories = ProductCategory.objects.filter(is_active=True)
    
    context = {
        'products': products,
        'categories': categories,
        'search': search,
        'selected_category': category,
        'selected_status': status,
        'stock_alert': stock_alert,
    }
    
    return render(request, 'stocks/product_list.html', context)


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def product_create(request):
    """Create new product."""
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save()
            messages.success(request, f'Producto "{product.name}" creado correctamente.')
            return redirect('stocks:product_list')
    else:
        form = ProductForm()
    
    return render(request, 'stocks/product_form.html', {
        'form': form,
        'title': 'Nuevo Producto'
    })


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def product_edit(request, pk):
    """Edit product."""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, f'Producto "{product.name}" actualizado correctamente.')
            return redirect('stocks:product_list')
    else:
        form = ProductForm(instance=product)
    
    return render(request, 'stocks/product_form.html', {
        'form': form,
        'title': 'Editar Producto',
        'product': product
    })


@login_required
@group_required(['Admin', 'Manager'])
def product_delete(request, pk):
    """Delete product (soft delete)."""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        product.is_active = False
        product.save()
        messages.success(request, f'Producto "{product.name}" desactivado correctamente.')
        return redirect('stocks:product_list')
    
    return render(request, 'stocks/product_confirm_delete.html', {'product': product})


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def product_detail(request, pk):
    """Product detail view."""
    product = get_object_or_404(Product, pk=pk)
    movements = product.stock_movements.order_by('-created_at')[:20]
    
    return render(request, 'stocks/product_detail.html', {
        'product': product,
        'movements': movements
    })


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def stock_adjust(request, pk):
    """Adjust product stock."""
    product = get_object_or_404(Product, pk=pk)
    
    if request.method == 'POST':
        form = StockAdjustmentForm(request.POST)
        if form.is_valid():
            new_quantity = form.cleaned_data['new_quantity']
            reason = form.cleaned_data['reason']
            
            StockManagementService.adjust_stock(
                product=product,
                new_quantity=new_quantity,
                reason=reason,
                user=request.user
            )
            
            messages.success(request, f'Stock de "{product.name}" ajustado correctamente.')
            return redirect('stocks:product_detail', pk=pk)
    else:
        form = StockAdjustmentForm(initial={'new_quantity': product.current_stock})
    
    return render(request, 'stocks/stock_adjust.html', {
        'form': form,
        'product': product
    })


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def category_list(request):
    """List categories."""
    categories = ProductCategory.objects.all()
    return render(request, 'stocks/category_list.html', {'categories': categories})


@login_required
@group_required(['Admin', 'Manager'])
def category_create(request):
    """Create category."""
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save()
            messages.success(request, f'Categoría "{category.name}" creada correctamente.')
            return redirect('stocks:category_list')
    else:
        form = CategoryForm()
    
    return render(request, 'stocks/category_form.html', {
        'form': form,
        'title': 'Nueva Categoría'
    })


@login_required
@group_required(['Admin', 'Manager'])
def category_edit(request, pk):
    """Edit category."""
    category = get_object_or_404(ProductCategory, pk=pk)
    
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f'Categoría "{category.name}" actualizada correctamente.')
            return redirect('stocks:category_list')
    else:
        form = CategoryForm(instance=category)
    
    return render(request, 'stocks/category_form.html', {
        'form': form,
        'title': 'Editar Categoría',
        'category': category
    })


@login_required
def low_stock_products(request):
    """List products with low stock."""
    products = StockManagementService.get_low_stock_products()
    return render(request, 'stocks/low_stock.html', {'products': products})


@login_required
def price_list(request):
    """Price list view."""
    products = Product.objects.filter(is_active=True).select_related('category')
    
    category = request.GET.get('category', '')
    if category:
        products = products.filter(category_id=category)
    
    categories = ProductCategory.objects.filter(is_active=True)
    
    return render(request, 'stocks/price_list.html', {
        'products': products,
        'categories': categories,
        'selected_category': category
    })


# API Endpoints

@login_required
def api_search_products(request):
    """API: Search products."""
    query = request.GET.get('q', '')
    
    if not query or len(query) < 2:
        return JsonResponse({'products': []})
    
    products = Product.objects.filter(is_active=True)
    
    # Check if it's a barcode search (8-13 digits)
    if query.isdigit() and 8 <= len(query) <= 13:
        products = products.filter(barcode=query)
    else:
        products = products.filter(
            Q(name__icontains=query) |
            Q(sku__icontains=query) |
            Q(barcode__icontains=query)
        )
    
    products = products[:20]
    
    data = {
        'products': [
            {
                'id': p.id,
                'name': p.name,
                'sku': p.sku,
                'barcode': p.barcode or '',
                'sale_price': float(p.sale_price),
                'current_stock': float(p.current_stock),
                'unit': p.unit_of_measure.abbreviation if p.unit_of_measure else 'u'
            }
            for p in products
        ]
    }
    
    return JsonResponse(data)


@login_required
def api_generate_barcode(request):
    """API: Generate new barcode."""
    barcode = BarcodeService.generate_ean13()
    
    # Ensure it's unique
    while Product.objects.filter(barcode=barcode).exists():
        barcode = BarcodeService.generate_ean13()
    
    return JsonResponse({'barcode': barcode})


@login_required
def export_products_excel(request):
    """Export products to Excel."""
    import openpyxl
    from openpyxl.utils import get_column_letter
    from django.http import HttpResponse
    
    products = Product.objects.filter(is_active=True).select_related('category')
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Productos'
    
    # Headers
    headers = ['SKU', 'Código de Barras', 'Nombre', 'Categoría', 'Precio Compra', 
               'Precio Venta', 'Stock Actual', 'Stock Mínimo', 'Ubicación']
    
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = openpyxl.styles.Font(bold=True)
    
    # Data
    for row, product in enumerate(products, 2):
        ws.cell(row=row, column=1, value=product.sku)
        ws.cell(row=row, column=2, value=product.barcode or '')
        ws.cell(row=row, column=3, value=product.name)
        ws.cell(row=row, column=4, value=product.category.name if product.category else '')
        ws.cell(row=row, column=5, value=float(product.purchase_price))
        ws.cell(row=row, column=6, value=float(product.sale_price))
        ws.cell(row=row, column=7, value=float(product.current_stock))
        ws.cell(row=row, column=8, value=float(product.min_stock))
        ws.cell(row=row, column=9, value=product.location)
    
    # Auto-width columns
    for col in range(1, len(headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 15
    
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = 'attachment; filename=productos.xlsx'
    wb.save(response)
    
    return response
