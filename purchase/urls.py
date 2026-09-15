"""
Purchase URL Configuration
"""
from django.urls import path
from . import views

app_name = 'purchase'

urlpatterns = [
    # Suppliers
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/create/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/edit/', views.supplier_edit, name='supplier_edit'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),
    path('suppliers/<int:pk>/productos/', views.supplier_products, name='supplier_products'),
    path('suppliers/<int:pk>/productos/<int:link_pk>/quitar/', views.supplier_product_remove, name='supplier_product_remove'),

    # Purchases
    path('', views.purchase_list, name='purchase_list'),
    path('sugeridos/', views.purchase_suggested, name='purchase_suggested'),
    path('sugeridos/<int:supplier_id>/generar/', views.purchase_suggested_generate, name='purchase_suggested_generate'),
    path('create/', views.purchase_create, name='purchase_create'),
    path('<int:pk>/edit/', views.purchase_edit, name='purchase_edit'),
    path('<int:pk>/receive/', views.purchase_receive, name='purchase_receive'),
    path('<int:pk>/cancel/', views.purchase_cancel, name='purchase_cancel'),
    path('<int:pk>/', views.purchase_detail, name='purchase_detail'),
    
    # API
    path('api/products/search/', views.api_search_products, name='api_search_products'),
]
