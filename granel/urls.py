from django.urls import path
from . import views

app_name = 'granel'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('transfer/', views.transfer_form, name='transfer'),
    path('transfer/history/', views.transfer_history, name='transfer_history'),
    path('audit/', views.shrinkage_audit_form, name='audit'),
    path('audit/history/', views.audit_history, name='audit_history'),
    path('batches/', views.batch_list, name='batch_list'),
    path('batches/<int:product_id>/', views.batch_detail, name='batch_detail'),
    # API
    path('api/transfer/', views.api_transfer, name='api_transfer'),
    path('api/audit/', views.api_audit, name='api_audit'),
    path('api/bulk-products/', views.api_bulk_products, name='api_bulk_products'),
]
