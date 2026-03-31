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
from .models import StockBatch, BulkToGranelTransfer, ShrinkageAudit
from .services import GranelService, BatchService


@login_required
@stock_manager_required
def dashboard(request):
    """Dashboard de la caramelera: productos granel activos."""
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

        last_transfer = BulkToGranelTransfer.objects.filter(
            granel_product=p
        ).first()

        last_audit = ShrinkageAudit.objects.filter(
            granel_product=p
        ).first()

        # Check for missing critical configuration
        config_warnings = []
        if not p.is_bulk:
            config_warnings.append('No marcado como "Producto a Granel" (is_bulk)')
        if p.granel_price_weight_grams == 0:
            config_warnings.append('granel_price_weight_grams = 0')
        if p.weighted_avg_cost_per_gram == 0 and p.current_stock > 0:
            config_warnings.append('Costo ponderado = $0 (sin transferencias)')

        products_data.append({
            'product': p,
            'margin': margin,
            'last_transfer': last_transfer,
            'last_audit': last_audit,
            'config_warnings': config_warnings,
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

    granel_id = request.GET.get('granel')
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

    granel_id = request.GET.get('granel')
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
        stock_batches__quantity_remaining__gt=0
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
