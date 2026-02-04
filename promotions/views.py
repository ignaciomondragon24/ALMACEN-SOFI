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
        # Build mutable copy of POST data to fix field names
        post_data = request.POST.copy()
        
        # Map HTML form field names to model field names
        if 'buy_quantity' in post_data:
            post_data['quantity_required'] = post_data.get('buy_quantity', 2)
        if 'pay_quantity' in post_data:
            post_data['quantity_charged'] = post_data.get('pay_quantity', 1)
        if 'combo_price' in post_data:
            post_data['final_price'] = post_data.get('combo_price', '0')
        if 'discount_percent_simple' in post_data:
            post_data['discount_percent'] = post_data.get('discount_percent_simple', '0')
            
        # Set default status to active if not provided
        if not post_data.get('status'):
            post_data['status'] = 'active'
            
        # Handle products - convert comma-separated string to list
        products_str = post_data.get('products', '')
        product_ids = []
        if products_str:
            product_ids = [int(pid.strip()) for pid in products_str.split(',') if pid.strip().isdigit()]
            
        # Create promotion directly without the form for products
        try:
            from stocks.models import Product
            from decimal import Decimal
            
            promotion = Promotion(
                name=post_data.get('name', ''),
                description=post_data.get('description', ''),
                promo_type=post_data.get('promo_type', 'nxm'),
                status=post_data.get('status', 'active'),
                priority=int(post_data.get('priority', 50)),
                is_combinable=post_data.get('is_combinable') == 'on',
                # Days
                monday=post_data.get('monday') == 'on',
                tuesday=post_data.get('tuesday') == 'on',
                wednesday=post_data.get('wednesday') == 'on',
                thursday=post_data.get('thursday') == 'on',
                friday=post_data.get('friday') == 'on',
                saturday=post_data.get('saturday') == 'on',
                sunday=post_data.get('sunday') == 'on',
                # NxM config
                quantity_required=int(post_data.get('quantity_required', post_data.get('buy_quantity', 2))),
                quantity_charged=int(post_data.get('quantity_charged', post_data.get('pay_quantity', 1))),
                # Discounts
                discount_percent=Decimal(post_data.get('discount_percent', '0') or '0'),
                second_unit_discount=Decimal(post_data.get('second_unit_discount', '0') or '0'),
                final_price=Decimal(post_data.get('final_price', post_data.get('combo_price', '0')) or '0'),
                min_quantity=int(post_data.get('min_quantity', 1) or 1),
                created_by=request.user
            )
            
            # Handle dates
            start_date = post_data.get('start_date')
            end_date = post_data.get('end_date')
            if start_date:
                promotion.start_date = start_date
            if end_date:
                promotion.end_date = end_date
                
            promotion.save()
            
            # Add products
            if product_ids:
                products = Product.objects.filter(id__in=product_ids)
                for product in products:
                    PromotionProduct.objects.create(promotion=promotion, product=product)
            
            messages.success(request, f'Promoción "{promotion.name}" creada correctamente.')
            return redirect('promotions:promotion_list')
            
        except Exception as e:
            messages.error(request, f'Error al crear la promoción: {str(e)}')
            form = PromotionForm(post_data)
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
        post_data = request.POST.copy()
        
        # Handle products - convert comma-separated string to list
        products_str = post_data.get('products', '')
        product_ids = []
        if products_str:
            product_ids = [int(pid.strip()) for pid in products_str.split(',') if pid.strip().isdigit()]
        
        try:
            from stocks.models import Product
            from decimal import Decimal
            
            promotion.name = post_data.get('name', promotion.name)
            promotion.description = post_data.get('description', '')
            promotion.promo_type = post_data.get('promo_type', promotion.promo_type)
            promotion.status = post_data.get('status', promotion.status) or 'active'
            promotion.priority = int(post_data.get('priority', 50))
            promotion.is_combinable = post_data.get('is_combinable') == 'on'
            # Days
            promotion.monday = post_data.get('monday') == 'on'
            promotion.tuesday = post_data.get('tuesday') == 'on'
            promotion.wednesday = post_data.get('wednesday') == 'on'
            promotion.thursday = post_data.get('thursday') == 'on'
            promotion.friday = post_data.get('friday') == 'on'
            promotion.saturday = post_data.get('saturday') == 'on'
            promotion.sunday = post_data.get('sunday') == 'on'
            # NxM config
            promotion.quantity_required = int(post_data.get('quantity_required', post_data.get('buy_quantity', 2)))
            promotion.quantity_charged = int(post_data.get('quantity_charged', post_data.get('pay_quantity', 1)))
            # Discounts
            promotion.discount_percent = Decimal(post_data.get('discount_percent', '0') or '0')
            promotion.second_unit_discount = Decimal(post_data.get('second_unit_discount', '0') or '0')
            promotion.final_price = Decimal(post_data.get('final_price', post_data.get('combo_price', '0')) or '0')
            promotion.min_quantity = int(post_data.get('min_quantity', 1) or 1)
            
            # Handle dates
            start_date = post_data.get('start_date')
            end_date = post_data.get('end_date')
            promotion.start_date = start_date if start_date else None
            promotion.end_date = end_date if end_date else None
                
            promotion.save()
            
            # Update products
            PromotionProduct.objects.filter(promotion=promotion).delete()
            if product_ids:
                products = Product.objects.filter(id__in=product_ids)
                for product in products:
                    PromotionProduct.objects.create(promotion=promotion, product=product)
            
            messages.success(request, f'Promoción "{promotion.name}" actualizada correctamente.')
            return redirect('promotions:promotion_list')
            
        except Exception as e:
            messages.error(request, f'Error al actualizar la promoción: {str(e)}')
            form = PromotionForm(instance=promotion)
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
