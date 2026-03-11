"""
Stocks Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, F
from django.core.paginator import Paginator
from decimal import Decimal

from .models import Product, ProductCategory, UnitOfMeasure, StockMovement, ProductPackaging
from .forms import ProductForm, CategoryForm, UnitForm, StockAdjustmentForm, BulkStockLoadForm, ProductPackagingForm
from .services import StockManagementService, BarcodeService
from decorators.decorators import group_required


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager', 'Cashier', 'General Manager'])
def product_list(request):
    """List all products."""
    products = Product.objects.select_related('category', 'unit_of_measure')
    
    # Filters
    search = request.GET.get('search', '')
    category = request.GET.get('category', '')
    status = request.GET.get('status', '')
    stock_alert = request.GET.get('stock_alert', '')
    
    if search:
        if search.isdigit():
            products = products.filter(
                Q(sku__istartswith=search) |
                Q(barcode__istartswith=search)
            )
        else:
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
@group_required(['Admin', 'Manager', 'Stock Manager', 'General Manager'])
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
        new_quantity = request.POST.get('new_quantity')
        reason = request.POST.get('reason', '')
        notes = request.POST.get('notes', '')
        
        # Mapear motivos a texto legible
        reason_map = {
            'conteo_fisico': 'Conteo Físico / Inventario',
            'mercaderia_danada': 'Mercadería Dañada',
            'mercaderia_vencida': 'Mercadería Vencida',
            'robo_perdida': 'Robo / Pérdida',
            'devolucion': 'Devolución',
            'correccion_error': 'Corrección de Error',
            'consumo_interno': 'Consumo Interno',
            'otro': 'Otro',
        }
        
        reason_text = reason_map.get(reason, reason)
        if notes:
            reason_text = f"{reason_text}: {notes}"
        
        try:
            from decimal import Decimal
            new_quantity = Decimal(new_quantity)
            
            StockManagementService.adjust_stock(
                product=product,
                new_quantity=new_quantity,
                reason=reason_text,
                user=request.user
            )
            
            messages.success(request, f'Stock de "{product.name}" ajustado correctamente.')
            return redirect('stocks:product_detail', pk=pk)
        except Exception as e:
            messages.error(request, f'Error al ajustar stock: {str(e)}')
    
    form = StockAdjustmentForm(initial={'new_quantity': product.current_stock})
    
    return render(request, 'stocks/stock_adjust.html', {
        'form': form,
        'product': product
    })


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager', 'General Manager'])
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
@group_required(['Admin', 'Manager', 'Stock Manager'])
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
    
    # Check if it's a barcode search (8-13 digits) - exact match
    if query.isdigit() and 8 <= len(query) <= 13:
        products = products.filter(barcode=query)
    elif query.isdigit():
        products = products.filter(
            Q(sku__istartswith=query) |
            Q(barcode__istartswith=query)
        )
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


# ==================== CARGA DE STOCK POR BULTOS ====================

@login_required
@group_required(['Admin', 'Stock Manager', 'Manager', 'General Manager'])
def bulk_stock_load(request):
    """Vista para carga rápida de stock por bultos."""
    
    if request.method == 'POST':
        form = BulkStockLoadForm(request.POST)
        if form.is_valid():
            barcode = form.cleaned_data['barcode']
            bulk_qty = form.cleaned_data['bulk_quantity']
            purchase_price = form.cleaned_data.get('purchase_price_per_bulk')
            margin_percent = form.cleaned_data['margin_percent']
            notes = form.cleaned_data.get('notes', '')
            
            # Buscar el empaque por código de barras
            try:
                packaging = ProductPackaging.objects.select_related('product').get(
                    barcode=barcode,
                    is_active=True
                )
                
                # Actualizar precios si se proporcionaron
                if purchase_price and purchase_price > 0:
                    packaging.purchase_price = purchase_price
                    packaging.margin_percent = margin_percent
                    
                    # Calcular precio de venta
                    packaging.sale_price = purchase_price * (1 + margin_percent / 100)
                    packaging.save()
                
                # Calcular cantidades
                total_units = packaging.calculate_total_units(bulk_qty)
                total_displays = packaging.calculate_displays(bulk_qty)
                
                # Actualizar stock del producto
                product = packaging.product
                old_stock = product.current_stock
                product.current_stock += total_units
                
                # Actualizar precios del producto (precio por unidad)
                if packaging.unit_purchase_price > 0:
                    product.purchase_price = packaging.unit_purchase_price
                if packaging.unit_sale_price > 0:
                    product.sale_price = packaging.unit_sale_price
                
                product.save()
                
                # Registrar movimiento de stock
                StockMovement.objects.create(
                    product=product,
                    movement_type='purchase',
                    quantity=total_units,
                    unit_cost=packaging.unit_purchase_price,
                    stock_before=old_stock,
                    stock_after=product.current_stock,
                    reference=f'Carga por Bultos - {bulk_qty} bultos ({packaging.name})',
                    notes=f'Displays: {total_displays} | {notes}' if total_displays > 0 else notes,
                    created_by=request.user
                )
                
                messages.success(
                    request,
                    f'Stock cargado exitosamente para {product.name}! '
                    f'Bultos: {bulk_qty} | Displays: {total_displays} | Unidades: {total_units} | '
                    f'Precio Unit.: ${packaging.unit_sale_price:.2f}'
                )
                
                return redirect('stocks:bulk_stock_load')
                
            except ProductPackaging.DoesNotExist:
                # Intentar buscar en el producto directamente
                try:
                    product = Product.objects.get(barcode=barcode, is_active=True)
                    messages.warning(
                        request,
                        f'El producto "{product.name}" no tiene empaques configurados. '
                        f'Configure los empaques primero.'
                    )
                    return redirect('stocks:packaging_config', product_id=product.id)
                except Product.DoesNotExist:
                    messages.error(
                        request,
                        f'No se encontró ningún producto o empaque con el código: {barcode}'
                    )
            except Exception as e:
                messages.error(request, f'Error al cargar stock: {str(e)}')
    else:
        form = BulkStockLoadForm()
    
    # Últimos movimientos de carga
    recent_loads = StockMovement.objects.filter(
        movement_type='purchase'
    ).select_related('product', 'created_by').order_by('-created_at')[:10]
    
    context = {
        'form': form,
        'recent_loads': recent_loads,
    }
    return render(request, 'stocks/bulk_stock_load.html', context)


@login_required
@group_required(['Admin', 'Stock Manager', 'Manager', 'General Manager'])
def packaging_config(request, product_id):
    """Configurar empaques para un producto."""
    
    product = get_object_or_404(Product, pk=product_id)
    
    if request.method == 'POST':
        packaging_type = request.POST.get('packaging_type')
        
        if packaging_type:
            # Verificar si ya existe este tipo de empaque
            existing = ProductPackaging.objects.filter(
                product=product, 
                packaging_type=packaging_type
            ).first()
            
            if existing:
                form = ProductPackagingForm(request.POST, instance=existing)
            else:
                form = ProductPackagingForm(request.POST)
            
            if form.is_valid():
                packaging = form.save(commit=False)
                packaging.product = product
                
                # Calcular precio de venta basado en margen
                if packaging.purchase_price > 0:
                    packaging.sale_price = packaging.purchase_price * (1 + packaging.margin_percent / 100)
                
                packaging.save()
                messages.success(request, f'Empaque {packaging.get_packaging_type_display()} guardado correctamente')
                return redirect('stocks:packaging_config', product_id=product.id)
            else:
                messages.error(request, 'Error en el formulario. Verifique los datos.')
    
    # Obtener empaques existentes
    unit_pkg = ProductPackaging.objects.filter(product=product, packaging_type='unit').first()
    display_pkg = ProductPackaging.objects.filter(product=product, packaging_type='display').first()
    bulk_pkg = ProductPackaging.objects.filter(product=product, packaging_type='bulk').first()
    
    context = {
        'product': product,
        'unit_pkg': unit_pkg,
        'display_pkg': display_pkg,
        'bulk_pkg': bulk_pkg,
        'form': ProductPackagingForm(),
    }
    return render(request, 'stocks/packaging_config.html', context)


@login_required
def api_lookup_packaging(request):
    """API para buscar información de empaque por código de barras."""
    
    barcode = request.GET.get('barcode', '').strip()
    
    if not barcode:
        return JsonResponse({'success': False, 'error': 'Código de barras requerido'}, status=400)
    
    def packaging_to_response(packaging):
        """Helper para convertir empaque a respuesta JSON."""
        prices = packaging.calculate_prices_from_margin()
        return {
            'success': True,
            'found_in': 'packaging',
            'product_id': packaging.product.id,
            'product_name': packaging.product.name,
            'product_sku': packaging.product.sku,
            'packaging_id': packaging.id,
            'packaging_type': packaging.packaging_type,
            'packaging_type_display': packaging.get_packaging_type_display(),
            'packaging_name': packaging.name,
            'units_quantity': packaging.units_quantity,
            'units_per_display': packaging.units_per_display,
            'displays_per_bulk': packaging.displays_per_bulk,
            'purchase_price': str(packaging.purchase_price),
            'sale_price': str(packaging.sale_price),
            'unit_purchase_price': str(packaging.unit_purchase_price),
            'unit_sale_price': str(packaging.unit_sale_price),
            'margin_percent': str(packaging.margin_percent),
            'current_stock': packaging.product.current_stock,
            'prices': prices,
        }
    
    try:
        # 1. Primero buscar en empaques por barcode exacto
        packaging = ProductPackaging.objects.select_related('product').filter(
            barcode=barcode,
            is_active=True
        ).first()
        
        if packaging:
            return JsonResponse(packaging_to_response(packaging))
        
        # 2. Si no está en empaques, buscar en productos
        product = Product.objects.filter(barcode=barcode, is_active=True).first()
        
        if product:
            # 3. Si el producto tiene empaques, devolver el empaque bulk (o el primero disponible)
            bulk_packaging = product.packagings.filter(
                packaging_type='bulk', is_active=True
            ).first()
            
            if bulk_packaging:
                response = packaging_to_response(bulk_packaging)
                response['scanned_product_barcode'] = True  # Indica que se escaneó el producto
                return JsonResponse(response)
            
            # Si no tiene bulk, buscar cualquier otro empaque
            any_packaging = product.packagings.filter(is_active=True).first()
            if any_packaging:
                response = packaging_to_response(any_packaging)
                response['scanned_product_barcode'] = True
                return JsonResponse(response)
            
            # No tiene empaques configurados
            data = {
                'success': True,
                'found_in': 'product',
                'product_id': product.id,
                'product_name': product.name,
                'product_sku': product.sku,
                'has_packagings': False,
                'current_stock': product.current_stock,
                'purchase_price': str(product.purchase_price),
                'sale_price': str(product.sale_price),
                'message': 'Producto sin empaques configurados'
            }
            return JsonResponse(data)
        
        return JsonResponse({
            'success': False,
            'error': 'No se encontró producto o empaque con ese código de barras'
        }, status=404)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def api_calculate_prices(request):
    """API para calcular precios basado en costo y margen."""
    
    try:
        purchase_price = Decimal(request.GET.get('purchase_price', '0'))
        margin_percent = Decimal(request.GET.get('margin_percent', '30'))
        units_per_display = int(request.GET.get('units_per_display', '1'))
        displays_per_bulk = int(request.GET.get('displays_per_bulk', '1'))
        
        if purchase_price <= 0:
            return JsonResponse({'success': False, 'error': 'Precio de compra inválido'})
        
        total_units = units_per_display * displays_per_bulk
        margin_multiplier = 1 + (margin_percent / 100)
        
        # Precio de venta del bulto
        bulk_sale = purchase_price * margin_multiplier
        
        # Calcular precios derivados
        unit_purchase = purchase_price / total_units if total_units > 0 else Decimal('0')
        unit_sale = bulk_sale / total_units if total_units > 0 else Decimal('0')
        
        display_purchase = purchase_price / displays_per_bulk if displays_per_bulk > 0 else Decimal('0')
        display_sale = bulk_sale / displays_per_bulk if displays_per_bulk > 0 else Decimal('0')
        
        data = {
            'success': True,
            'calculations': {
                'total_units': total_units,
                'total_displays': displays_per_bulk,
                'unit_purchase': str(unit_purchase.quantize(Decimal('0.01'))),
                'unit_sale': str(unit_sale.quantize(Decimal('0.01'))),
                'unit_profit': str((unit_sale - unit_purchase).quantize(Decimal('0.01'))),
                'display_purchase': str(display_purchase.quantize(Decimal('0.01'))),
                'display_sale': str(display_sale.quantize(Decimal('0.01'))),
                'display_profit': str((display_sale - display_purchase).quantize(Decimal('0.01'))),
                'bulk_purchase': str(purchase_price),
                'bulk_sale': str(bulk_sale.quantize(Decimal('0.01'))),
                'bulk_profit': str((bulk_sale - purchase_price).quantize(Decimal('0.01'))),
            }
        }
        return JsonResponse(data)
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@group_required(['Admin', 'Stock Manager', 'Manager', 'General Manager'])
def packaging_delete(request, packaging_id):
    """Eliminar un empaque."""
    
    packaging = get_object_or_404(ProductPackaging, pk=packaging_id)
    product_id = packaging.product.id
    packaging_name = str(packaging)
    
    if request.method == 'POST':
        packaging.delete()
        messages.success(request, f'Empaque "{packaging_name}" eliminado.')
        return redirect('stocks:packaging_config', product_id=product_id)
    
    return redirect('stocks:packaging_config', product_id=product_id)


@login_required
@group_required(['Admin', 'Stock Manager', 'Manager', 'General Manager'])
def api_create_product_with_packaging(request):
    """
    API para crear un producto nuevo con su estructura de empaques (bulto, display, unidad).
    """
    import json
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
        
        # Validar datos requeridos
        product_name = data.get('product_name', '').strip()
        bulk_barcode = data.get('bulk_barcode', '').strip()
        units_per_display = int(data.get('units_per_display', 1))
        displays_per_bulk = int(data.get('displays_per_bulk', 1))
        purchase_price = Decimal(str(data.get('purchase_price', 0)))
        margin_percent = Decimal(str(data.get('margin_percent', 30)))
        category_id = data.get('category_id')
        
        # Códigos opcionales
        display_barcode = data.get('display_barcode', '').strip()
        unit_barcode = data.get('unit_barcode', '').strip()
        
        if not product_name:
            return JsonResponse({'success': False, 'error': 'El nombre del producto es requerido'})
        
        if not bulk_barcode:
            return JsonResponse({'success': False, 'error': 'El código de barras del bulto es requerido'})
        
        # Verificar que el código de barras no exista
        if ProductPackaging.objects.filter(barcode=bulk_barcode).exists():
            return JsonResponse({'success': False, 'error': 'El código de barras del bulto ya existe'})
        
        if display_barcode and ProductPackaging.objects.filter(barcode=display_barcode).exists():
            return JsonResponse({'success': False, 'error': 'El código de barras del display ya existe'})
        
        if unit_barcode and ProductPackaging.objects.filter(barcode=unit_barcode).exists():
            return JsonResponse({'success': False, 'error': 'El código de barras de la unidad ya existe'})
        
        # Verificar en productos también
        if Product.objects.filter(barcode=bulk_barcode).exists():
            return JsonResponse({'success': False, 'error': 'El código de barras del bulto ya existe en productos'})
        
        # Calcular totales
        total_units = units_per_display * displays_per_bulk
        margin_multiplier = 1 + (margin_percent / 100)
        bulk_sale = purchase_price * margin_multiplier if purchase_price > 0 else Decimal('0')
        
        unit_purchase = purchase_price / total_units if total_units > 0 and purchase_price > 0 else Decimal('0')
        unit_sale = bulk_sale / total_units if total_units > 0 and bulk_sale > 0 else Decimal('0')
        
        # Generar SKU
        import uuid
        sku = f"PKG-{uuid.uuid4().hex[:8].upper()}"
        
        # Crear el producto
        category = None
        if category_id:
            category = ProductCategory.objects.filter(pk=category_id).first()
        
        unit_of_measure = UnitOfMeasure.objects.filter(abbreviation='u').first()
        if not unit_of_measure:
            unit_of_measure = UnitOfMeasure.objects.first()
        
        product = Product.objects.create(
            sku=sku,
            barcode=unit_barcode if unit_barcode else None,
            name=product_name,
            category=category,
            unit_of_measure=unit_of_measure,
            purchase_price=unit_purchase,
            sale_price=unit_sale,
            current_stock=0,
            min_stock=10,
            is_active=True,
        )
        
        # Crear packaging de BULTO
        bulk_packaging = ProductPackaging.objects.create(
            product=product,
            packaging_type='bulk',
            barcode=bulk_barcode,
            name=f'Bulto x {total_units}',
            units_quantity=total_units,
            units_per_display=units_per_display,
            displays_per_bulk=displays_per_bulk,
            purchase_price=purchase_price,
            sale_price=bulk_sale,
            margin_percent=margin_percent,
            is_default=False,
            is_active=True,
        )
        
        # Crear packaging de DISPLAY (si tiene código)
        display_packaging = None
        if display_barcode:
            display_purchase = purchase_price / displays_per_bulk if displays_per_bulk > 0 and purchase_price > 0 else Decimal('0')
            display_sale = bulk_sale / displays_per_bulk if displays_per_bulk > 0 and bulk_sale > 0 else Decimal('0')
            
            display_packaging = ProductPackaging.objects.create(
                product=product,
                packaging_type='display',
                barcode=display_barcode,
                name=f'Display x {units_per_display}',
                units_quantity=units_per_display,
                units_per_display=units_per_display,
                displays_per_bulk=1,
                purchase_price=display_purchase,
                sale_price=display_sale,
                margin_percent=margin_percent,
                is_default=False,
                is_active=True,
            )
        
        # Crear packaging de UNIDAD (si tiene código)
        unit_packaging = None
        if unit_barcode:
            unit_packaging = ProductPackaging.objects.create(
                product=product,
                packaging_type='unit',
                barcode=unit_barcode,
                name='Unidad',
                units_quantity=1,
                units_per_display=1,
                displays_per_bulk=1,
                purchase_price=unit_purchase,
                sale_price=unit_sale,
                margin_percent=margin_percent,
                is_default=True,
                is_active=True,
            )
        
        return JsonResponse({
            'success': True,
            'product_id': product.id,
            'product_name': product.name,
            'bulk_packaging_id': bulk_packaging.id,
            'display_packaging_id': display_packaging.id if display_packaging else None,
            'unit_packaging_id': unit_packaging.id if unit_packaging else None,
            'message': f'Producto "{product_name}" creado con empaques configurados.'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
