"""
Stocks URLs
"""
from django.urls import path
from . import views

app_name = 'stocks'

urlpatterns = [
    # Products
    path('', views.product_list, name='product_list'),
    path('add/', views.product_create, name='product_create'),
    path('<int:pk>/', views.product_detail, name='product_detail'),
    path('<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('<int:pk>/adjust/', views.stock_adjust, name='stock_adjust'),
    
    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_edit, name='category_edit'),
    
    # Reports
    path('low-stock/', views.low_stock_products, name='low_stock'),
    path('price-list/', views.price_list, name='price_list'),
    path('export/excel/', views.export_products_excel, name='export_excel'),
    
    # API
    path('api/search/', views.api_search_products, name='api_search'),
    path('api/generate-barcode/', views.api_generate_barcode, name='generate_barcode'),
]
