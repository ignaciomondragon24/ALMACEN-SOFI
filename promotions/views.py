"""
Promotions Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
import json

from .models import Promotion, PromotionProduct
from .forms import PromotionForm
from .engine import PromotionEngine
from decorators.decorators import group_required


@login_required
@group_required(['Admin', 'Manager'])
def promotion_list(request):
    """List all promotions."""
    promotions = Promotion.objects.all()
    
    # Filters
    status = request.GET.get('status', '')
    promo_type = request.GET.get('type', '')
    
    if status:
        promotions = promotions.filter(status=status)
    if promo_type:
        promotions = promotions.filter(promo_type=promo_type)
    
    context = {
        'promotions': promotions,
        'selected_status': status,
        'selected_type': promo_type,
    }
    
    return render(request, 'promotions/promotion_list.html', context)


@login_required
@group_required(['Admin', 'Manager'])
def promotion_create(request):
    """Create new promotion."""
    if request.method == 'POST':
        form = PromotionForm(request.POST)
        if form.is_valid():
            promotion = form.save(commit=False)
            promotion.created_by = request.user
            promotion.save()
            
            # Handle products
            products = form.cleaned_data.get('products')
            if products:
                for product in products:
                    PromotionProduct.objects.create(promotion=promotion, product=product)
            
            messages.success(request, f'Promoción "{promotion.name}" creada correctamente.')
            return redirect('promotions:promotion_list')
    else:
        form = PromotionForm()
    
    return render(request, 'promotions/promotion_form.html', {
        'form': form,
        'title': 'Nueva Promoción'
    })


@login_required
@group_required(['Admin', 'Manager'])
def promotion_edit(request, pk):
    """Edit promotion."""
    promotion = get_object_or_404(Promotion, pk=pk)
    
    if request.method == 'POST':
        form = PromotionForm(request.POST, instance=promotion)
        if form.is_valid():
            promotion = form.save()
            
            # Update products
            PromotionProduct.objects.filter(promotion=promotion).delete()
            products = form.cleaned_data.get('products')
            if products:
                for product in products:
                    PromotionProduct.objects.create(promotion=promotion, product=product)
            
            messages.success(request, f'Promoción "{promotion.name}" actualizada correctamente.')
            return redirect('promotions:promotion_list')
    else:
        initial_products = promotion.products.all()
        form = PromotionForm(instance=promotion, initial={'products': initial_products})
    
    return render(request, 'promotions/promotion_form.html', {
        'form': form,
        'title': 'Editar Promoción',
        'promotion': promotion
    })


@login_required
@group_required(['Admin', 'Manager'])
def promotion_detail(request, pk):
    """Promotion detail."""
    promotion = get_object_or_404(Promotion, pk=pk)
    products = promotion.products.all()
    
    return render(request, 'promotions/promotion_detail.html', {
        'promotion': promotion,
        'products': products
    })


@login_required
@group_required(['Admin', 'Manager'])
def promotion_delete(request, pk):
    """Delete promotion."""
    promotion = get_object_or_404(Promotion, pk=pk)
    
    if request.method == 'POST':
        name = promotion.name
        promotion.delete()
        messages.success(request, f'Promoción "{name}" eliminada correctamente.')
        return redirect('promotions:promotion_list')
    
    return render(request, 'promotions/promotion_confirm_delete.html', {
        'promotion': promotion
    })


@login_required
@group_required(['Admin', 'Manager'])
@require_POST
def promotion_activate(request, pk):
    """Activate promotion."""
    promotion = get_object_or_404(Promotion, pk=pk)
    promotion.status = 'active'
    promotion.save()
    messages.success(request, f'Promoción "{promotion.name}" activada.')
    return redirect('promotions:promotion_list')


@login_required
@group_required(['Admin', 'Manager'])
@require_POST
def promotion_pause(request, pk):
    """Pause promotion."""
    promotion = get_object_or_404(Promotion, pk=pk)
    promotion.status = 'paused'
    promotion.save()
    messages.success(request, f'Promoción "{promotion.name}" pausada.')
    return redirect('promotions:promotion_list')


@login_required
def api_calculate(request):
    """API: Calculate promotions for cart items."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    
    cart_items = data.get('cart_items', [])
    
    result = PromotionEngine.calculate_cart(cart_items)
    
    return JsonResponse(result)
