"""
Context Processors for Accounts
Provides permission context to all templates
"""


def role_context(request):
    """Add user permissions to template context."""
    if not request.user.is_authenticated:
        return {
            'is_admin': False,
            'is_manager': False,
            'is_cashier': False,
            'is_stock_manager': False,
            'is_general_manager': False,
        }
    
    user = request.user
    user_groups = list(user.groups.values_list('name', flat=True))
    
    # Role checks
    is_admin = user.is_superuser or user.is_admin or 'Admin' in user_groups
    is_manager = is_admin or 'Manager' in user_groups
    is_general_manager = is_admin or 'General Manager' in user_groups
    is_cashier = is_admin or is_manager or 'Cashier' in user_groups
    is_stock_manager = is_admin or is_manager or 'Stock Manager' in user_groups
    
    return {
        'user_roles': user_groups,
        'is_admin_user': is_admin,
        
        # Role flags for templates
        'is_admin': is_admin,
        'is_manager': is_manager,
        'is_general_manager': is_general_manager,
        'is_cashier': is_cashier,
        'is_stock_manager': is_stock_manager,
        
        # Module permissions
        'can_pos': is_cashier,
        'can_cash': is_cashier,
        'can_stocks': is_stock_manager,
        'can_purchases': is_manager or is_stock_manager,
        'can_expenses': is_manager,
        'can_promotions': is_manager,
        'can_signage': is_manager or is_stock_manager,
        'can_sales': is_manager or is_general_manager,
        'can_reports': is_manager or is_general_manager,
        'can_settings': is_admin,
        'can_users': is_admin,
        'can_price_list': is_cashier or is_stock_manager,
    }
