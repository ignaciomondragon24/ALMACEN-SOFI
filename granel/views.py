"""
Granel Views - Caramelera management.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from decimal import Decimal
import json

from stocks.models import Product
from decorators.decorators import stock_manager_required
from .models import StockBatch, BulkToGranelTransfer, ShrinkageAudit, CarameleraComponent
from .services import GranelService, BatchService


@login_required
@stock_manager_required
def dashboard(request):
    """Dashboard de la caramelera: productos granel activos con sus componentes."""
    granel_products = Product.objects.filter(
        is_active=True, is_granel=True
    ).order_by('name')

    products_data = []
    for p in granel_products:
        margin = Decimal('0')
        if p.weighted_avg_cost_per_gram > 0 and p.granel_price_weight_grams > 0:
            cost_per_unit = p.weighted_avg_cost_per_gram * p.granel_price_weight_grams
            if cost_per_unit > 0:
                margin = ((p.sale_price - cost_per_unit) / cost_per_unit * 100).quantize(Decimal('0.1'))

        last_transfer = BulkToGranelTransfer.objects.filter(granel_product=p).first()
        last_audit = ShrinkageAudit.objects.filter(granel_product=p).first()

        components = CarameleraComponent.objects.filter(
            caramelera=p
        ).select_related('bulk_product')

        products_data.append({
            'product': p,
            'margin': margin,
            'last_transfer': last_transfer,
            'last_audit': last_audit,
            'components': components,
        })

    return render(request, 'granel/dashboard.html', {
        'products_data': products_data,
    })


@login_required
@stock_manager_required
def transfer_form(request):
    """Formulario de apertura de bulto (transferencia a granel)."""
    granel_products = Product.objects.filter(
        is_active=True, is_granel=True
    ).order_by('name')

    bulk_products = Product.objects.filter(
        is_active=True,
        weight_per_unit_grams__gt=0,
        current_stock__gt=0,
    ).order_by('name')

    # Prerequisite warnings
    warnings = []
    if not granel_products.exists():
        warnings.append(
            'No hay productos granel configurados. '
            'Edita un producto y activa "Producto Comodin Granel" para que aparezca como destino.'
        )
    if not bulk_products.exists():
        warnings.append(
            'No hay bultos disponibles para transferir. '
            'Asegurate de que al menos un producto tenga "Peso por Unidad (g)" > 0 y stock > 0.'
        )

    return render(request, 'granel/transfer_form.html', {
        'granel_products': granel_products,
        'bulk_products': bulk_products,
        'warnings': warnings,
    })


@login_required
@stock_manager_required
def transfer_history(request):
    """Historial de transferencias bulto a granel."""
    transfers = BulkToGranelTransfer.objects.select_related(
        'bulk_product', 'granel_product', 'source_batch', 'transferred_by'
    ).all()

    granel_id = (request.GET.get('granel') or '').replace('.', '').strip() or None
    if granel_id:
        transfers = transfers.filter(granel_product_id=granel_id)

    return render(request, 'granel/transfer_history.html', {
        'transfers': transfers[:100],
        'granel_products': Product.objects.filter(is_active=True, is_granel=True),
        'current_granel': granel_id,
    })


@login_required
@stock_manager_required
def shrinkage_audit_form(request):
    """Formulario de auditoría de mermas."""
    granel_products = Product.objects.filter(
        is_active=True, is_granel=True
    ).order_by('name')

    warnings = []
    if not granel_products.filter(current_stock__gt=0).exists():
        warnings.append(
            'No hay carameleras con stock para auditar. '
            'Primero transfiere stock abriendo un bulto.'
        )

    return render(request, 'granel/shrinkage_audit_form.html', {
        'granel_products': granel_products,
        'reason_choices': ShrinkageAudit.REASON_CHOICES,
        'warnings': warnings,
    })


@login_required
@stock_manager_required
def audit_history(request):
    """Historial de auditorías de merma."""
    audits = ShrinkageAudit.objects.select_related(
        'granel_product', 'audited_by'
    ).all()

    granel_id = (request.GET.get('granel') or '').replace('.', '').strip() or None
    if granel_id:
        audits = audits.filter(granel_product_id=granel_id)

    return render(request, 'granel/audit_history.html', {
        'audits': audits[:100],
        'granel_products': Product.objects.filter(is_active=True, is_granel=True),
        'current_granel': granel_id,
    })


@login_required
@stock_manager_required
def batch_list(request):
    """Lista de productos con lotes activos."""
    products_with_batches = Product.objects.filter(
        batches__quantity_remaining__gt=0
    ).distinct().order_by('name')

    return render(request, 'granel/batch_list.html', {
        'products': products_with_batches,
    })


@login_required
@stock_manager_required
def batch_detail(request, product_id):
    """Detalle de lotes para un producto."""
    product = get_object_or_404(Product, pk=product_id)
    batches = StockBatch.objects.filter(product=product).order_by('purchased_at')
    active_batches = batches.filter(quantity_remaining__gt=0)
    depleted_batches = batches.filter(quantity_remaining__lte=0)[:20]

    return render(request, 'granel/batch_detail.html', {
        'product': product,
        'active_batches': active_batches,
        'depleted_batches': depleted_batches,
    })


# ======================== API Endpoints ========================

@login_required
@stock_manager_required
@require_POST
def api_transfer(request):
    """API: ejecutar transferencia bulto -> granel."""
    try:
        data = json.loads(request.body)
        bulk_product_id = data.get('bulk_product_id')
        granel_product_id = data.get('granel_product_id')
        notes = data.get('notes', '')

        if not bulk_product_id or not granel_product_id:
            return JsonResponse({'error': 'Faltan datos'}, status=400)

        transfer = GranelService.transfer_bulk_to_granel(
            bulk_product_id=bulk_product_id,
            granel_product_id=granel_product_id,
            user=request.user,
            notes=notes,
        )

        return JsonResponse({
            'success': True,
            'transfer': {
                'id': transfer.pk,
                'grams': float(transfer.grams_transferred),
                'cost_per_gram': float(transfer.bulk_cost_per_gram),
                'new_stock': float(transfer.granel_stock_after),
                'new_avg_cost': float(transfer.granel_weighted_cost_after),
            }
        })
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)


@login_required
@stock_manager_required
@require_POST
def api_audit(request):
    """API: ejecutar auditoría de merma."""
    try:
        data = json.loads(request.body)
        granel_product_id = data.get('granel_product_id')
        actual_grams = data.get('actual_grams')
        reason = data.get('reason', 'otro')
        notes = data.get('notes', '')

        if not granel_product_id or actual_grams is None:
            return JsonResponse({'error': 'Faltan datos'}, status=400)

        audit = GranelService.perform_shrinkage_audit(
            granel_product_id=granel_product_id,
            actual_grams=actual_grams,
            reason=reason,
            notes=notes,
            user=request.user,
        )

        return JsonResponse({
            'success': True,
            'audit': {
                'id': audit.pk,
                'theoretical': float(audit.theoretical_grams),
                'actual': float(audit.actual_grams),
                'shrinkage': float(audit.shrinkage_grams),
                'percent': float(audit.shrinkage_percent),
            }
        })
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)


@login_required
@stock_manager_required
def manage_components(request, product_id):
    """Ver y gestionar qué bultos componen una caramelera."""
    caramelera = get_object_or_404(Product, pk=product_id, is_granel=True)
    components = CarameleraComponent.objects.filter(
        caramelera=caramelera
    ).select_related('bulk_product')

    # Productos bulto candidatos (tienen peso configurado y están activos)
    existing_ids = components.values_list('bulk_product_id', flat=True)
    available_bulk = Product.objects.filter(
        is_active=True,
        weight_per_unit_grams__gt=0,
    ).exclude(pk__in=existing_ids).order_by('name')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'add':
            bulk_id = (request.POST.get('bulk_product_id') or '').replace('.', '').strip()
            notes = request.POST.get('notes', '')
            if bulk_id:
                CarameleraComponent.objects.get_or_create(
                    caramelera=caramelera,
                    bulk_product_id=bulk_id,
                    defaults={'notes': notes},
                )
        elif action == 'remove':
            component_id = (request.POST.get('component_id') or '').replace('.', '').strip()
            CarameleraComponent.objects.filter(pk=component_id, caramelera=caramelera).delete()
        from django.shortcuts import redirect
        return redirect('granel:manage_components', product_id=product_id)

    return render(request, 'granel/manage_components.html', {
        'caramelera': caramelera,
        'components': components,
        'available_bulk': available_bulk,
    })


@login_required
@stock_manager_required
@require_POST
def api_quick_transfer(request, component_id):
    """API: abrir un paquete de golmitas para una caramelera (un solo click)."""
    try:
        component = CarameleraComponent.objects.select_related(
            'caramelera', 'bulk_product'
        ).get(pk=component_id)

        if component.bulk_product.current_stock < 1:
            return JsonResponse({
                'error': f'Sin stock de {component.bulk_product.name}'
            }, status=400)

        notes = json.loads(request.body).get('notes', '') if request.body else ''
        transfer = GranelService.transfer_bulk_to_granel(
            bulk_product_id=component.bulk_product_id,
            granel_product_id=component.caramelera_id,
            user=request.user,
            notes=notes,
        )

        return JsonResponse({
            'success': True,
            'transfer': {
                'id': transfer.pk,
                'grams': float(transfer.grams_transferred),
                'cost_per_gram': float(transfer.bulk_cost_per_gram),
                'new_stock': float(transfer.granel_stock_after),
                'new_avg_cost': float(transfer.granel_weighted_cost_after),
                'bulk_stock_remaining': float(component.bulk_product.current_stock),
            }
        })
    except CarameleraComponent.DoesNotExist:
        return JsonResponse({'error': 'Componente no encontrado'}, status=404)
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@stock_manager_required
@require_GET
def api_bulk_products(request):
    """API: obtener productos bulto disponibles para un granel."""
    bulk_products = Product.objects.filter(
        is_active=True,
        weight_per_unit_grams__gt=0,
        current_stock__gt=0,
    ).order_by('name')

    return JsonResponse({
        'products': [
            {
                'id': p.id,
                'name': p.name,
                'stock': float(p.current_stock),
                'weight_grams': float(p.weight_per_unit_grams),
                'cost_price': float(p.cost_price),
            }
            for p in bulk_products
        ]
    })


# ======================== Caramelera Create / Edit ========================

@login_required
@stock_manager_required
def caramelera_list(request):
    """Lista de carameleras activas."""
    carameleras = (
        Product.objects.filter(is_active=True, is_granel=True)
        .prefetch_related('components__bulk_product')
        .order_by('name')
    )
    return render(request, 'granel/caramelera_list.html', {'carameleras': carameleras})


@login_required
@stock_manager_required
def caramelera_create(request):
    """Formulario para crear una nueva caramelera."""
    bulk_products = Product.objects.filter(
        is_active=True, weight_per_unit_grams__gt=0
    ).order_by('name')
    return render(request, 'granel/caramelera_form.html', {
        'title': 'Nueva Caramelera',
        'bulk_products': bulk_products,
        'caramelera': None,
        'components_json': '[]',
    })


@login_required
@stock_manager_required
def caramelera_edit(request, pk):
    """Formulario para editar una caramelera existente."""
    import json as _json
    caramelera = get_object_or_404(Product, pk=pk, is_granel=True)
    components = list(
        CarameleraComponent.objects.filter(caramelera=caramelera)
        .select_related('bulk_product')
    )
    bulk_products = Product.objects.filter(
        is_active=True, weight_per_unit_grams__gt=0
    ).order_by('name')

    components_data = []
    for c in components:
        cpg = 0
        if c.bulk_product.weight_per_unit_grams:
            cpg = float(c.bulk_product.cost_price / c.bulk_product.weight_per_unit_grams)
        components_data.append({
            'product_id': c.bulk_product_id,
            'name': c.bulk_product.name,
            'proportion_grams': float(c.proportion_grams),
            'cost_per_gram': cpg,
        })

    return render(request, 'granel/caramelera_form.html', {
        'title': f'Editar {caramelera.name}',
        'bulk_products': bulk_products,
        'caramelera': caramelera,
        'components_json': _json.dumps(components_data),
    })


@login_required
@stock_manager_required
@require_POST
def api_caramelera_save(request, pk=None):
    """API: crear o actualizar una caramelera con sus componentes."""
    from django.db import transaction as db_transaction
    try:
        data = json.loads(request.body)
        name = (data.get('name') or '').strip()
        sale_price_100g = Decimal(str(data.get('sale_price_100g', '0')))
        sale_price_250g = Decimal(str(data.get('sale_price_250g', '0')))
        rows = data.get('rows', [])

        if not name:
            return JsonResponse({'error': 'El nombre es obligatorio.'}, status=400)
        if sale_price_100g <= 0:
            return JsonResponse({'error': 'El precio por 100g debe ser mayor a 0.'}, status=400)
        if not rows:
            return JsonResponse({'error': 'Agregá al menos un producto.'}, status=400)

        validated = []
        total_grams = Decimal('0')
        total_cost = Decimal('0')
        for row in rows:
            pid = row.get('product_id')
            grams = Decimal(str(row.get('proportion_grams', '0')))
            if not pid or grams <= 0:
                return JsonResponse(
                    {'error': 'Cada fila necesita producto y gramos > 0.'}, status=400
                )
            try:
                p = Product.objects.get(pk=pid, is_active=True, weight_per_unit_grams__gt=0)
            except Product.DoesNotExist:
                return JsonResponse({'error': f'Producto {pid} no válido.'}, status=400)
            cpg = p.cost_price / p.weight_per_unit_grams
            validated.append({'product': p, 'grams': grams, 'cpg': cpg})
            total_grams += grams
            total_cost += grams * cpg

        weighted_cpg = (total_cost / total_grams).quantize(Decimal('0.0001'))

        with db_transaction.atomic():
            if pk:
                caramelera = get_object_or_404(Product, pk=pk, is_granel=True)
            else:
                base = 'GRAM-' + ''.join(
                    c for c in name.upper() if c.isalnum() or c == ' '
                ).replace(' ', '-')[:12]
                sku = base
                i = 1
                while Product.objects.filter(sku=sku).exists():
                    sku = f'{base}-{i}'
                    i += 1
                caramelera = Product(sku=sku, is_granel=True, granel_price_weight_grams=100)

            caramelera.name = name
            caramelera.sale_price = sale_price_100g
            caramelera.sale_price_250g = sale_price_250g
            caramelera.weighted_avg_cost_per_gram = weighted_cpg
            caramelera.cost_price = (weighted_cpg * 100).quantize(Decimal('0.01'))
            caramelera.is_active = True
            caramelera.save()

            CarameleraComponent.objects.filter(caramelera=caramelera).delete()
            for r in validated:
                CarameleraComponent.objects.create(
                    caramelera=caramelera,
                    bulk_product=r['product'],
                    proportion_grams=r['grams'],
                )

        return JsonResponse({'success': True, 'pk': caramelera.pk, 'name': caramelera.name})

    except (ValueError, Exception) as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@stock_manager_required
def caramelera_detail(request, pk):
    """Vista detallada de una caramelera: stock, componentes, historial de aperturas."""
    caramelera = get_object_or_404(Product, pk=pk, is_granel=True)
    components = (
        CarameleraComponent.objects.filter(caramelera=caramelera)
        .select_related('bulk_product')
    )
    recent_transfers = (
        BulkToGranelTransfer.objects.filter(granel_product=caramelera)
        .select_related('bulk_product', 'transferred_by')[:20]
    )
    # All bulk products with stock > 0 (for "abrir bolsa" modal)
    bulk_available = Product.objects.filter(
        is_active=True, weight_per_unit_grams__gt=0, current_stock__gt=0
    ).order_by('name')

    return render(request, 'granel/caramelera_detail.html', {
        'caramelera': caramelera,
        'components': components,
        'recent_transfers': recent_transfers,
        'bulk_available': bulk_available,
    })


@login_required
@stock_manager_required
@require_POST
def api_abrir_bolsa(request, pk):
    """API: abrir una bolsa y sumar gramos a la caramelera."""
    caramelera = get_object_or_404(Product, pk=pk, is_granel=True)
    try:
        data = json.loads(request.body)
        bulk_id = int(str(data.get('bulk_product_id', '')).replace('.', '').strip())
        grams = Decimal(str(data.get('grams', '0')))
        notes = data.get('notes', '')

        transfer = GranelService.abrir_bolsa(
            bulk_product_id=bulk_id,
            granel_product_id=caramelera.pk,
            grams=grams,
            user=request.user,
            notes=notes,
        )
        caramelera.refresh_from_db()
        bulk = Product.objects.get(pk=bulk_id)
        return JsonResponse({
            'success': True,
            'grams_added': float(transfer.grams_transferred),
            'new_stock': float(caramelera.current_stock),
            'new_avg_cost': float(caramelera.weighted_avg_cost_per_gram),
            'bulk_stock_remaining': float(bulk.current_stock),
            'bulk_name': bulk.name,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
