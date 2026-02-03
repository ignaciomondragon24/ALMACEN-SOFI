"""
Accounts Views - Login, Dashboard, User Management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from .models import User, Role
from .forms import LoginForm, UserForm, UserEditForm
from decorators.decorators import group_required


def login_view(request):
    """User login view."""
    if request.user.is_authenticated:
        return redirect('accounts:home')
    
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            user = authenticate(request, username=username, password=password)
            
            if user is not None:
                if user.is_active:
                    login(request, user)
                    messages.success(request, f'¡Bienvenido, {user.get_full_name()}!')
                    
                    # Redirect to next URL if provided
                    next_url = request.GET.get('next')
                    if next_url:
                        return redirect(next_url)
                    return redirect('accounts:home')
                else:
                    messages.error(request, 'Tu cuenta está desactivada.')
            else:
                messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = LoginForm()
    
    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """User logout view."""
    logout(request)
    messages.info(request, 'Has cerrado sesión correctamente.')
    return redirect('accounts:login')


@login_required
def home_view(request):
    """Dashboard principal - redirige al dashboard."""
    return redirect('accounts:dashboard')


@login_required
def dashboard_view(request):
    """Dashboard principal con estadísticas según el rol del usuario."""
    # Importamos aquí para evitar imports circulares
    from pos.models import POSTransaction
    from stocks.models import Product, ProductCategory
    from cashregister.models import CashShift
    from promotions.models import Promotion
    from django.db import models
    
    user = request.user
    user_groups = list(user.groups.values_list('name', flat=True))
    is_admin = user.is_superuser or user.is_admin or 'Admin' in user_groups
    is_manager = is_admin or 'Manager' in user_groups
    is_cashier = 'Cashier' in user_groups
    is_stock_manager = 'Stock Manager' in user_groups
    
    today = timezone.now().date()
    context = {}
    
    # Turno actual del usuario (para cajeros)
    user_shift = CashShift.objects.filter(
        cashier=user,
        status='open'
    ).first()
    context['user_shift'] = user_shift
    
    # === DATOS PARA CAJEROS ===
    if is_cashier or is_manager or is_admin:
        # Mis ventas del día
        if user_shift:
            my_transactions = POSTransaction.objects.filter(
                session__cash_shift=user_shift,
                status='completed'
            )
            context['my_sales_today'] = my_transactions.aggregate(total=Sum('total'))['total'] or 0
            context['my_transactions_count'] = my_transactions.count()
        else:
            context['my_sales_today'] = 0
            context['my_transactions_count'] = 0
    
    # === DATOS PARA STOCK MANAGER ===
    if is_stock_manager or is_manager or is_admin:
        # Productos con bajo stock
        low_stock_products = Product.objects.filter(
            is_active=True,
            current_stock__lte=models.F('min_stock')
        ).select_related('category')[:10]
        context['low_stock_products'] = low_stock_products
        context['low_stock_count'] = Product.objects.filter(
            is_active=True,
            current_stock__lte=models.F('min_stock')
        ).count()
        context['total_products'] = Product.objects.filter(is_active=True).count()
        context['total_categories'] = ProductCategory.objects.filter(is_active=True).count()
    
    # === DATOS PARA MANAGERS Y ADMIN ===
    if is_manager or is_admin:
        # Ventas del día (global)
        today_transactions = POSTransaction.objects.filter(
            status='completed',
            completed_at__date=today
        )
        context['today_sales'] = today_transactions.aggregate(total=Sum('total'))['total'] or 0
        context['today_transactions'] = today_transactions.count()
        
        # Ventas recientes
        context['recent_sales'] = POSTransaction.objects.filter(
            status='completed'
        ).select_related(
            'session__cash_shift__cash_register',
            'session__cash_shift__cashier'
        ).order_by('-completed_at')[:5]
        
        # Turnos abiertos
        context['open_shifts'] = CashShift.objects.filter(status='open').select_related(
            'cash_register', 'cashier'
        )
        context['open_shifts_count'] = context['open_shifts'].count()
        
        # Promociones activas
        context['active_promotions'] = Promotion.objects.filter(status='active').count()
    
    # === DATOS PARA ADMIN ===
    if is_admin:
        # Usuarios activos
        context['active_users'] = User.objects.filter(is_active=True).count()
        # Cajas registradas
        from cashregister.models import CashRegister
        context['total_registers'] = CashRegister.objects.filter(is_active=True).count()
    
    return render(request, 'accounts/dashboard.html', context)


@login_required
@group_required(['Admin', 'Manager'])
def user_list(request):
    """Lista de usuarios."""
    users = User.objects.all().prefetch_related('groups')
    return render(request, 'accounts/user_list.html', {'users': users})


@login_required
@group_required(['Admin'])
def user_create(request):
    """Crear nuevo usuario."""
    if request.method == 'POST':
        form = UserForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            
            # Asignar rol
            role_name = form.cleaned_data.get('role')
            if role_name:
                role = Role.objects.get(name=role_name)
                user.groups.add(role)
            
            messages.success(request, f'Usuario {user.username} creado correctamente.')
            return redirect('accounts:user_list')
    else:
        form = UserForm()
    
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Crear Usuario'
    })


@login_required
@group_required(['Admin'])
def user_edit(request, pk):
    """Editar usuario."""
    user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            user = form.save()
            
            # Actualizar rol
            user.groups.clear()
            role_name = form.cleaned_data.get('role')
            if role_name:
                role = Role.objects.get(name=role_name)
                user.groups.add(role)
            
            messages.success(request, f'Usuario {user.username} actualizado correctamente.')
            return redirect('accounts:user_list')
    else:
        initial_role = user.groups.first().name if user.groups.exists() else None
        form = UserEditForm(instance=user, initial={'role': initial_role})
    
    return render(request, 'accounts/user_form.html', {
        'form': form,
        'title': 'Editar Usuario',
        'editing': True
    })


@login_required
@group_required(['Admin'])
def user_delete(request, pk):
    """Eliminar usuario (soft delete)."""
    user = get_object_or_404(User, pk=pk)
    
    if request.method == 'POST':
        user.is_active = False
        user.save()
        messages.success(request, f'Usuario {user.username} desactivado correctamente.')
        return redirect('accounts:user_list')
    
    return render(request, 'accounts/user_confirm_delete.html', {'user': user})


@login_required
def profile_view(request):
    """Ver y editar perfil propio."""
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        messages.success(request, 'Perfil actualizado correctamente.')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/profile.html')


@login_required
def change_password(request):
    """Cambiar contraseña."""
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.user.check_password(current_password):
            messages.error(request, 'La contraseña actual es incorrecta.')
        elif new_password != confirm_password:
            messages.error(request, 'Las contraseñas nuevas no coinciden.')
        elif len(new_password) < 8:
            messages.error(request, 'La contraseña debe tener al menos 8 caracteres.')
        else:
            request.user.set_password(new_password)
            request.user.save()
            messages.success(request, 'Contraseña cambiada correctamente. Por favor inicia sesión nuevamente.')
            return redirect('accounts:login')
    
    return render(request, 'accounts/change_password.html')


# Importar models para usar en home_view
from django.db import models
