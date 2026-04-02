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
    path('<int:product_id>/components/', views.manage_components, name='manage_components'),
    # API
    path('api/transfer/', views.api_transfer, name='api_transfer'),
    path('api/audit/', views.api_audit, name='api_audit'),
    path('api/bulk-products/', views.api_bulk_products, name='api_bulk_products'),
    path('api/quick-transfer/<int:component_id>/', views.api_quick_transfer, name='api_quick_transfer'),
    # Caramelera create/edit
    path('carameleras/', views.caramelera_list, name='caramelera_list'),
    path('carameleras/create/', views.caramelera_create, name='caramelera_create'),
    path('carameleras/<int:pk>/edit/', views.caramelera_edit, name='caramelera_edit'),
    path('api/caramelera/save/', views.api_caramelera_save, name='api_caramelera_save'),
    path('api/caramelera/<int:pk>/save/', views.api_caramelera_save, name='api_caramelera_save_edit'),
]
