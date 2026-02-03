"""
POS URLs
"""
from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    # Main POS view
    path('', views.pos_main, name='main'),
    path('', views.pos_main, name='pos_main'),  # Alias for compatibility
    
    # Suspended transactions
    path('suspended/', views.suspended_transactions, name='suspended'),
    
    # API endpoints
    path('api/search/', views.api_search, name='api_search'),
    path('api/cart/add/', views.api_cart_add, name='api_cart_add'),
    path('api/cart/add-by-amount/', views.api_cart_add_by_amount, name='api_cart_add_by_amount'),
    path('api/calculate-by-amount/', views.api_calculate_by_amount, name='api_calculate_by_amount'),
    path('api/cart/item/<int:item_id>/', views.api_cart_update, name='api_cart_update'),
    path('api/cart/item/<int:item_id>/remove/', views.api_cart_remove, name='api_cart_remove'),
    path('api/cart/<int:transaction_id>/clear/', views.api_cart_clear, name='api_cart_clear'),
    path('api/transaction/<int:transaction_id>/', views.api_transaction_detail, name='api_transaction_detail'),
    path('api/checkout/', views.api_checkout, name='api_checkout'),
    path('api/transaction/<int:transaction_id>/suspend/', views.api_transaction_suspend, name='api_transaction_suspend'),
    path('api/transaction/<int:transaction_id>/resume/', views.api_transaction_resume, name='api_transaction_resume'),
    path('api/transaction/<int:transaction_id>/cancel/', views.api_transaction_cancel, name='api_transaction_cancel'),
]
