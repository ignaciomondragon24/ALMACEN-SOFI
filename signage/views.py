"""
Signage Views - Diseñador Visual de Carteles
"""
import json
from decimal import Decimal, InvalidOperation

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .models import SignTemplate, SignBatch, SignItem
from stocks.models import Product, ProductCategory
from decorators.decorators import group_required

SIGN_ROLES = ['Admin', 'Manager', 'Stock Manager', 'General Manager']


# ---------------------------------------------------------------------------
# Home
# ---------------------------------------------------------------------------
@login_required
@group_required(SIGN_ROLES)
def signage_home(request):
    templates = SignTemplate.objects.filter(is_active=True)
    recent_batches = (
        SignBatch.objects.filter(created_by=request.user)
        .select_related('template')
        .order_by('-created_at')[:10]
    )
    return render(request, 'signage/home.html', {
        'templates': templates,
        'recent_batches': recent_batches,
    })


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------
@login_required
@group_required(SIGN_ROLES)
def template_list(request):
    templates = SignTemplate.objects.filter(is_active=True)
    return render(request, 'signage/template_list.html', {
        'templates': templates,
    })


@login_required
@group_required(SIGN_ROLES)
def designer(request, pk=None):
    """Visual template designer – create or edit."""
    template = None
    if pk:
        template = get_object_or_404(SignTemplate, pk=pk)

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        template_type = request.POST.get('template_type', 'simple')
        width_mm = int(request.POST.get('width_mm', 50))
        height_mm = int(request.POST.get('height_mm', 40))
        layout_raw = request.POST.get('layout_json', '{}')

        if not name:
            messages.error(request, 'El nombre de la plantilla es obligatorio.')
            return render(request, 'signage/designer.html', {
                'template': template,
                'template_types': SignTemplate.TEMPLATE_TYPES,
                'default_layouts': _all_default_layouts(),
            })

        try:
            layout = json.loads(layout_raw)
        except json.JSONDecodeError:
            layout = SignTemplate.get_default_layout(template_type)

        if template is None:
            template = SignTemplate(created_by=request.user)

        template.name = name
        template.template_type = template_type
        template.width_mm = max(20, min(width_mm, 300))
        template.height_mm = max(20, min(height_mm, 300))
        template.set_layout(layout)
        template.save()

        messages.success(request, f'Plantilla "{template.name}" guardada correctamente.')
        return redirect('signage:template_list')

    return render(request, 'signage/designer.html', {
        'template': template,
        'template_types': SignTemplate.TEMPLATE_TYPES,
        'default_layouts': _all_default_layouts(),
    })


@login_required
@group_required(['Admin', 'Manager', 'General Manager'])
def template_delete(request, pk):
    template = get_object_or_404(SignTemplate, pk=pk)
    if request.method == 'POST':
        template.is_active = False
        template.save(update_fields=['is_active'])
        messages.success(request, f'Plantilla "{template.name}" eliminada.')
    return redirect('signage:template_list')


# ---------------------------------------------------------------------------
# API – Template defaults (AJAX)
# ---------------------------------------------------------------------------
@login_required
def api_template_defaults(request):
    ttype = request.GET.get('type', 'simple')
    layout = SignTemplate.get_default_layout(ttype)
    w, h = SignTemplate.get_default_dimensions(ttype)
    return JsonResponse({'layout': layout, 'width_mm': w, 'height_mm': h})


# ---------------------------------------------------------------------------
# Generator – Select template, add products, create batch
# ---------------------------------------------------------------------------
@login_required
@group_required(SIGN_ROLES)
def generator(request, template_pk=None):
    """Sign generator – pick a template and add products."""
    template = None
    if template_pk:
        template = get_object_or_404(SignTemplate, pk=template_pk, is_active=True)

    templates = SignTemplate.objects.filter(is_active=True)
    categories = ProductCategory.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True).select_related('category').order_by('name')

    return render(request, 'signage/generator.html', {
        'selected_template': template,
        'templates': templates,
        'categories': categories,
        'products': products,
    })


@login_required
@group_required(SIGN_ROLES)
@require_POST
def create_batch(request):
    """Create a batch of signs from submitted form data."""
    template_pk = request.POST.get('template_pk')
    paper_size = request.POST.get('paper_size', 'A4')
    items_json = request.POST.get('items_json', '[]')

    template = get_object_or_404(SignTemplate, pk=template_pk, is_active=True)

    try:
        items_data = json.loads(items_json)
    except json.JSONDecodeError:
        messages.error(request, 'Datos de carteles inválidos.')
        return redirect('signage:generator_with_template', template_pk=template.pk)

    if not items_data:
        messages.error(request, 'Agregá al menos un producto para generar carteles.')
        return redirect('signage:generator_with_template', template_pk=template.pk)

    batch = SignBatch.objects.create(
        template=template,
        paper_size=paper_size,
        created_by=request.user,
    )

    for idx, item in enumerate(items_data):
        product_id = item.get('product_id')
        product = None
        if product_id:
            try:
                product = Product.objects.get(pk=int(product_id), is_active=True)
            except (Product.DoesNotExist, ValueError, TypeError):
                pass

        SignItem.objects.create(
            batch=batch,
            product=product,
            custom_name=item.get('custom_name', ''),
            custom_price=_safe_decimal(item.get('custom_price')),
            gramaje=item.get('gramaje', ''),
            promo_quantity=_safe_int(item.get('promo_quantity')),
            promo_price=_safe_decimal(item.get('promo_price')),
            package_type=item.get('package_type', ''),
            quantity_per_package=item.get('quantity_per_package', ''),
            price_100g=_safe_decimal(item.get('price_100g')),
            price_250g=_safe_decimal(item.get('price_250g')),
            price_1kg=_safe_decimal(item.get('price_1kg')),
            copies=max(1, _safe_int(item.get('copies')) or 1),
            order=idx,
        )

    return redirect('signage:preview_batch', pk=batch.pk)


# ---------------------------------------------------------------------------
# Preview & Print
# ---------------------------------------------------------------------------
@login_required
@group_required(SIGN_ROLES)
def preview_batch(request, pk):
    batch = get_object_or_404(SignBatch.objects.select_related('template'), pk=pk)
    items = batch.items.select_related('product').all()
    layout = batch.template.get_layout()

    return render(request, 'signage/preview_batch.html', {
        'batch': batch,
        'items': items,
        'layout': layout,
        'layout_json': json.dumps(layout, ensure_ascii=False),
        'template': batch.template,
    })


@login_required
@group_required(SIGN_ROLES)
def print_layout(request, pk):
    batch = get_object_or_404(SignBatch.objects.select_related('template'), pk=pk)
    items = batch.items.select_related('product').all()
    layout = batch.template.get_layout()
    paper_w, paper_h = batch.get_paper_dimensions()
    margin_mm = 5
    sign_w = batch.template.width_mm
    sign_h = batch.template.height_mm
    gap = 2

    cols = max(1, (paper_w - 2 * margin_mm + gap) // (sign_w + gap))
    rows = max(1, (paper_h - 2 * margin_mm + gap) // (sign_h + gap))
    per_page = cols * rows

    # Build expanded list (respecting copies)
    expanded = []
    for item in items:
        for _ in range(item.copies):
            expanded.append(item)

    # Split into pages
    pages = []
    for i in range(0, len(expanded), per_page):
        pages.append(expanded[i:i + per_page])

    return render(request, 'signage/print_layout.html', {
        'batch': batch,
        'pages': pages,
        'layout': layout,
        'layout_json': json.dumps(layout, ensure_ascii=False),
        'template': batch.template,
        'cols': cols,
        'rows': rows,
        'per_page': per_page,
        'paper_w': paper_w,
        'paper_h': paper_h,
        'margin_mm': margin_mm,
        'sign_w': sign_w,
        'sign_h': sign_h,
        'gap': gap,
    })


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------
@login_required
@group_required(SIGN_ROLES)
def history(request):
    batches = (
        SignBatch.objects.select_related('template', 'created_by')
        .order_by('-created_at')
    )
    return render(request, 'signage/history.html', {'batches': batches})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _all_default_layouts():
    return json.dumps({
        t: SignTemplate.get_default_layout(t)
        for t in ('simple', 'promotional', 'bulk', 'weight')
    }, ensure_ascii=False)


def _safe_decimal(val):
    if val is None or val == '':
        return None
    try:
        return Decimal(str(val).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None


def _safe_int(val):
    if val is None or val == '':
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
