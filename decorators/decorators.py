"""
Custom Decorators for CHE GOLOSO
"""
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied


def group_required(*group_names):
    """
    Decorator that checks if user belongs to any of the specified groups.
    
    Usage:
        @group_required('Admin', 'Manager')
        def my_view(request):
            ...
        
        # Also supports list syntax:
        @group_required(['Admin', 'Manager'])
        def my_view(request):
            ...
    """
    # Handle case where a list is passed as a single argument
    if len(group_names) == 1 and isinstance(group_names[0], (list, tuple)):
        group_names = tuple(group_names[0])
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            
            # Superusers have access to everything
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Check if user belongs to any of the required groups
            if request.user.groups.filter(name__in=group_names).exists():
                return view_func(request, *args, **kwargs)
            
            messages.error(
                request,
                'No tiene permisos para acceder a esta sección.'
            )
            raise PermissionDenied
        
        return wrapper
    return decorator


def admin_required(view_func):
    """Decorator that requires Admin group."""
    return group_required('Admin')(view_func)


def manager_required(view_func):
    """Decorator that requires Admin or Cajero Manager group."""
    return group_required('Admin', 'Cajero Manager')(view_func)


def cashier_required(view_func):
    """Decorator that requires Cashier, Cajero Manager, or Admin group."""
    return group_required('Admin', 'Cajero Manager', 'Cashier')(view_func)


def stock_manager_required(view_func):
    """Decorator that requires stock access: Cajero Manager or Admin group."""
    return group_required('Admin', 'Cajero Manager')(view_func)


def ajax_login_required(view_func):
    """
    Decorator for AJAX views that returns JSON error if not authenticated.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            from django.http import JsonResponse
            return JsonResponse({
                'success': False,
                'error': 'Autenticación requerida'
            }, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper


def open_shift_required(view_func):
    """
    Decorator that checks if user has an open cash shift.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from cashregister.models import CashShift
        
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        
        # Check for open shift
        open_shift = CashShift.objects.filter(
            cashier=request.user,
            status='open'
        ).first()
        
        if not open_shift:
            messages.warning(
                request,
                'Debe abrir una caja para continuar.'
            )
            return redirect('cashregister:shift_open')
        
        # Add shift to request for easy access
        request.cash_shift = open_shift
        return view_func(request, *args, **kwargs)
    
    return wrapper
