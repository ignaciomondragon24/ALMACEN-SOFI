import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST

from decorators.decorators import group_required
from .models import SignTemplate, SignBatch, SignItem
from .forms import SignTemplateForm
from .services import auto_fill_product_data


@login_required
@group_required('Admin', 'Manager', 'Stock Manager')
def template_list(request):
    """Lista de plantillas de carteles."""
    templates = SignTemplate.objects.filter(is_active=True)
    return render(request, 'signage/template_list.html', {
        'templates': templates,
        'sign_types': SignTemplate.SIGN_TYPES,
    })


@login_required
@group_required('Admin', 'Manager', 'Stock Manager')
def template_create(request):
    """Crear una nueva plantilla (paso 1: elegir tipo y tamaño)."""
    if request.method == 'POST':
        form = SignTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.created_by = request.user
            template.layout_json = '{}'
            template.save()
            return redirect('signage:designer', pk=template.pk)
    else:
        form = SignTemplateForm()

    return render(request, 'signage/template_form.html', {
        'form': form,
        'preset_sizes': json.dumps(SignTemplate.PRESET_SIZES),
        'sign_types': SignTemplate.SIGN_TYPES,
    })


@login_required
@group_required('Admin', 'Manager', 'Stock Manager')
def designer(request, pk):
    """Diseñador visual estilo Canva."""
    template = get_object_or_404(SignTemplate, pk=pk)
    variables = SignTemplate.get_type_variables(template.sign_type)

    return render(request, 'signage/designer.html', {
        'template': template,
        'layout_json': json.dumps(template.layout),
        'variables': variables,
        'variables_json': json.dumps(variables),
    })


@login_required
@require_POST
def save_layout(request, pk):
    """API: Guardar layout del diseñador."""
    template = get_object_or_404(SignTemplate, pk=pk)
    try:
        data = json.loads(request.body)
        layout = data.get('layout', {})

        if 'name' in data and data['name']:
            template.name = data['name'][:200]
        if 'width_mm' in data:
            template.width_mm = max(10, int(data['width_mm']))
        if 'height_mm' in data:
            template.height_mm = max(10, int(data['height_mm']))

        template.layout_json = json.dumps(layout)
        template.save()
        return JsonResponse({'success': True})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)


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
