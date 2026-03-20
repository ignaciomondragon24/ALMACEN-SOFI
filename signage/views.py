import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST

from decorators.decorators import group_required
from .models import SignTemplate, SignBatch, SignItem, ensure_default_templates
from .services import auto_fill_product_data


@login_required
@group_required('Admin', 'Manager', 'Stock Manager')
def template_list(request):
    """Catálogo de plantillas pre-armadas."""
    ensure_default_templates()
    templates = SignTemplate.objects.filter(is_active=True).order_by('sign_type', 'width_mm')
    # Solo mostrar plantillas con layout completo
    templates = [t for t in templates if t.layout.get('elements')]

    # Agrupar por tipo
    type_meta = {
        'simple': {'icon': 'fa-tag', 'color': '#2D1E5F'},
        'promo': {'icon': 'fa-fire', 'color': '#E91E8C'},
        'bulk': {'icon': 'fa-box', 'color': '#F5D000'},
        'weight': {'icon': 'fa-balance-scale', 'color': '#28a745'},
    }

    grouped = []
    seen_types = set()
    for t in templates:
        if t.sign_type not in seen_types:
            meta = type_meta.get(t.sign_type, {'icon': 'fa-tag', 'color': '#666'})
            grouped.append({
                'type_key': t.sign_type,
                'label': t.get_sign_type_display(),
                'icon': meta['icon'],
                'color': meta['color'],
                'templates': [],
            })
            seen_types.add(t.sign_type)
        # Append to last group
        for g in grouped:
            if g['type_key'] == t.sign_type:
                g['templates'].append(t)
                break

    return render(request, 'signage/template_list.html', {
        'grouped': grouped,
    })


@login_required
@group_required('Admin', 'Manager', 'Stock Manager')
def template_delete(request, pk):
    """Eliminar (desactivar) una plantilla."""
    template = get_object_or_404(SignTemplate, pk=pk)
    if request.method == 'POST':
        template.is_active = False
        template.save()
        messages.success(request, f'Plantilla "{template.name}" eliminada.')
        return redirect('signage:template_list')
    return render(request, 'signage/template_confirm_delete.html', {
        'template': template,
    })


@login_required
@group_required('Admin', 'Manager', 'Stock Manager')
def generate(request, pk):
    """Generar carteles a partir de una plantilla."""
    template = get_object_or_404(SignTemplate, pk=pk)
    variables = SignTemplate.get_type_variables(template.sign_type)

    return render(request, 'signage/generate.html', {
        'template': template,
        'layout_json': json.dumps(template.layout),
        'variables': variables,
        'variables_json': json.dumps(variables),
    })


@login_required
def api_product_data(request):
    """API: Auto-completar datos de producto para un tipo de cartel."""
    from stocks.models import Product

    product_id = request.GET.get('product_id')
    sign_type = request.GET.get('sign_type', 'simple')

    if not product_id:
        return JsonResponse({'error': 'product_id requerido'}, status=400)

    try:
        product = Product.objects.get(pk=product_id)
        data = auto_fill_product_data(product, sign_type)
        return JsonResponse({
            'success': True,
            'product_id': product.pk,
            'product_name': product.name,
            'data': data,
        })
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Producto no encontrado'}, status=404)


@login_required
@group_required('Admin', 'Manager', 'Stock Manager')
def print_view(request):
    """Vista de impresión optimizada con nesting."""
    return render(request, 'signage/print_preview.html')


@login_required
@group_required('Admin', 'Manager', 'Stock Manager')
def batch_list(request):
    """Historial de lotes generados."""
    batches = SignBatch.objects.select_related('template', 'created_by')
    return render(request, 'signage/batch_list.html', {
        'batches': batches,
    })


@login_required
@require_POST
def save_batch(request):
    """API: Guardar un lote de carteles."""
    try:
        data = json.loads(request.body)
        template_id = data.get('template_id')
        if not template_id:
            return JsonResponse({'error': 'template_id requerido'}, status=400)

        template = get_object_or_404(SignTemplate, pk=template_id)

        batch = SignBatch.objects.create(
            template=template,
            name=data.get('name', f'Lote {template.name}')[:200],
            paper_size=data.get('paper_size', 'A4'),
            created_by=request.user,
        )

        for i, item_data in enumerate(data.get('items', [])):
            product_id = item_data.get('product_id')
            SignItem.objects.create(
                batch=batch,
                product_id=product_id if product_id else None,
                data_json=json.dumps(item_data.get('data', {})),
                copies=max(1, int(item_data.get('copies', 1))),
                order=i,
            )

        return JsonResponse({'success': True, 'batch_id': batch.pk})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
