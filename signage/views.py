"""
Signage Views
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse

from .models import SignTemplate, SignGeneration
from stocks.models import Product, ProductCategory
from decorators.decorators import group_required


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def signage_home(request):
    """Signage home page."""
    templates = SignTemplate.objects.filter(is_active=True)
    recent_generations = SignGeneration.objects.filter(
        generated_by=request.user
    ).order_by('-generated_at')[:10]
    
    return render(request, 'signage/home.html', {
        'templates': templates,
        'recent_generations': recent_generations
    })


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def generate_sign(request):
    """Generate new sign."""
    templates = SignTemplate.objects.filter(is_active=True)
    categories = ProductCategory.objects.filter(is_active=True)
    products = Product.objects.filter(is_active=True)
    
    if request.method == 'POST':
        template_id = request.POST.get('template')
        product_ids = request.POST.getlist('products')
        
        if not template_id or not product_ids:
            messages.error(request, 'Selecciona una plantilla y al menos un producto.')
            return redirect('signage:generate')
        
        template = get_object_or_404(SignTemplate, pk=template_id)
        
        # Create generation record
        generation = SignGeneration.objects.create(
            template=template,
            generated_by=request.user
        )
        generation.products.set(product_ids)
        
        # TODO: Generate actual PDF
        # For now, redirect to preview
        messages.success(request, 'Cartel generado correctamente.')
        return redirect('signage:preview', pk=generation.pk)
    
    return render(request, 'signage/generate.html', {
        'templates': templates,
        'categories': categories,
        'products': products
    })


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def preview_sign(request, pk):
    """Preview generated sign."""
    generation = get_object_or_404(SignGeneration, pk=pk)
    products = generation.products.all()
    
    return render(request, 'signage/preview.html', {
        'generation': generation,
        'products': products
    })


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def download_sign(request, pk):
    """Download generated sign PDF."""
    generation = get_object_or_404(SignGeneration, pk=pk)
    
    # TODO: Generate and return actual PDF
    # For now, return a simple text response
    response = HttpResponse(content_type='text/plain')
    response['Content-Disposition'] = f'attachment; filename="cartel_{pk}.txt"'
    
    content = "CARTEL DE PRECIOS\n"
    content += "=" * 40 + "\n\n"
    
    for product in generation.products.all():
        content += f"{product.name}\n"
        content += f"Código: {product.sku}\n"
        content += f"Precio: ${product.sale_price}\n"
        content += "-" * 20 + "\n"
    
    response.write(content)
    return response


@login_required
@group_required(['Admin', 'Manager', 'Stock Manager'])
def history(request):
    """Sign generation history."""
    generations = SignGeneration.objects.all().order_by('-generated_at')
    
    return render(request, 'signage/history.html', {
        'generations': generations
    })


@login_required
@group_required(['Admin', 'Manager'])
def template_list(request):
    """List all templates."""
    templates = SignTemplate.objects.all()
    
    return render(request, 'signage/template_list.html', {
        'templates': templates
    })
