"""
Signage Views - Sistema de Cartelería
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from decimal import Decimal
import json

from .models import SignTemplate, SignGeneration
from stocks.models import Product, ProductCategory
from promotions.models import Promotion
from decorators.decorators import group_required


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager', 'General Manager'])
def signage_home(request):
    """Página principal de cartelería con accesos rápidos."""
    templates = SignTemplate.objects.filter(is_active=True)
    recent_generations = SignGeneration.objects.filter(
        generated_by=request.user
    ).order_by('-generated_at')[:10]
    
    # Obtener promociones activas para mostrar
    active_promos = Promotion.objects.filter(status='active')
    
    return render(request, 'signage/home.html', {
        'templates': templates,
        'recent_generations': recent_generations,
        'active_promos': active_promos
    })


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager', 'General Manager'])
def generate_sign(request):
    """Generar cartel - interfaz principal mejorada."""
    categories = ProductCategory.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True).order_by('name')
    promotions = Promotion.objects.filter(status='active')
    
    if request.method == 'POST':
        sign_type = request.POST.get('sign_type', 'price')
        product_ids = request.POST.getlist('products')
        promotion_id = request.POST.get('promotion')
        custom_text = request.POST.get('custom_text', '')
        sign_size = request.POST.get('sign_size', 'A4')
        
        # Crear registro de generación
        generation = SignGeneration.objects.create(
            generated_by=request.user,
            sign_type=sign_type,
            sign_size=sign_size,
            custom_text=custom_text
        )
        
        if product_ids:
            generation.products.set(product_ids)
        
        if promotion_id:
            generation.promotion_id = promotion_id
            generation.save()
        
        return redirect('signage:preview', pk=generation.pk)
    
    return render(request, 'signage/generate.html', {
        'categories': categories,
        'products': products,
        'promotions': promotions
    })


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager', 'General Manager'])
def preview_sign(request, pk):
    """Vista previa del cartel generado."""
    generation = get_object_or_404(SignGeneration, pk=pk)
    products = generation.products.all()
    promotion = generation.promotion
    
    # Preparar datos para el cartel
    sign_data = []
    
    for product in products:
        item = {
            'product': product,
            'name': product.name,
            'price': product.sale_price,
            'old_price': None,
            'promo_text': None,
            'promo_type': None,
            'discount_percent': None,
        }
        
        # Si hay promoción, calcular datos
        if promotion:
            item['promo_type'] = promotion.promo_type
            
            if promotion.promo_type == 'nxm':
                # Promociones NxM (2x1, 3x2, etc)
                item['promo_text'] = f"{promotion.quantity_required}x{promotion.quantity_charged}"
                if promotion.quantity_charged == 1:
                    item['promo_text'] = f"{promotion.quantity_required}x1"
                # Calcular precio efectivo
                effective_price = (product.sale_price * promotion.quantity_charged) / promotion.quantity_required
                savings_percent = ((product.sale_price - effective_price) / product.sale_price) * 100
                item['discount_percent'] = int(savings_percent)
                
            elif promotion.promo_type == 'second_unit':
                # Segunda unidad con descuento
                discount = promotion.second_unit_discount
                item['promo_text'] = f"2da unidad {int(discount)}% OFF"
                item['discount_percent'] = int(discount / 2)  # Promedio
                
            elif promotion.promo_type == 'simple_discount':
                # Descuento simple
                discount = promotion.discount_percent
                item['promo_text'] = f"{int(discount)}% OFF"
                item['old_price'] = product.sale_price
                item['price'] = product.sale_price * (1 - discount / 100)
                item['discount_percent'] = int(discount)
                
            elif promotion.promo_type == 'combo':
                # Combo
                if promotion.final_price:
                    item['promo_text'] = "COMBO"
                    item['price'] = promotion.final_price
        
        sign_data.append(item)
    
    return render(request, 'signage/preview.html', {
        'generation': generation,
        'products': products,
        'promotion': promotion,
        'sign_data': sign_data,
        'sign_type': generation.sign_type,
        'sign_size': generation.sign_size,
    })


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager', 'General Manager'])
def download_sign(request, pk):
    """Descargar cartel como HTML imprimible."""
    generation = get_object_or_404(SignGeneration, pk=pk)
    products = generation.products.all()
    promotion = generation.promotion
    
    # Preparar datos
    sign_data = []
    for product in products:
        item = {
            'name': product.name,
            'price': product.sale_price,
            'old_price': None,
            'promo_text': None,
        }
        
        if promotion:
            if promotion.promo_type == 'nxm':
                item['promo_text'] = f"{promotion.quantity_required}x{promotion.quantity_charged}"
            elif promotion.promo_type == 'second_unit':
                item['promo_text'] = f"2da unidad {int(promotion.second_unit_discount)}% OFF"
            elif promotion.promo_type == 'simple_discount':
                item['promo_text'] = f"{int(promotion.discount_percent)}% OFF"
                item['old_price'] = product.sale_price
                item['price'] = product.sale_price * (1 - promotion.discount_percent / 100)
        
        sign_data.append(item)
    
    # Generar HTML para imprimir
    html_content = render_to_string('signage/print_sign.html', {
        'generation': generation,
        'sign_data': sign_data,
        'promotion': promotion,
        'sign_type': generation.sign_type,
    })
    
    response = HttpResponse(html_content, content_type='text/html')
    return response


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager', 'General Manager'])
def quick_promo_sign(request, promo_id):
    """Generar cartel rápido desde una promoción."""
    promotion = get_object_or_404(Promotion, pk=promo_id)
    
    # Obtener productos de la promoción
    products = promotion.products.all()
    
    if not products.exists():
        messages.error(request, 'Esta promoción no tiene productos asociados.')
        return redirect('signage:home')
    
    # Crear generación
    generation = SignGeneration.objects.create(
        generated_by=request.user,
        sign_type='promotion',
        sign_size='A4',
        promotion=promotion
    )
    generation.products.set(products)
    
    return redirect('signage:preview', pk=generation.pk)


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager', 'General Manager'])
def history(request):
    """Historial de carteles generados."""
    generations = SignGeneration.objects.all().order_by('-generated_at')
    
    return render(request, 'signage/history.html', {
        'generations': generations
    })


@login_required
@group_required(['Admin', 'Manager', 'General Manager'])
def template_list(request):
    """Lista de plantillas."""
    templates = SignTemplate.objects.all()
    
    return render(request, 'signage/template_list.html', {
        'templates': templates
    })
