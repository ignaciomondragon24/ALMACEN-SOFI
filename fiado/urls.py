"""
Fiado URLs
"""
from django.urls import path

from . import views

app_name = 'fiado'

urlpatterns = [
    path('', views.customer_list, name='customer_list'),
    path('nuevo/', views.customer_create, name='customer_create'),
    path('<int:pk>/', views.customer_detail, name='customer_detail'),
    path('<int:pk>/editar/', views.customer_edit, name='customer_edit'),
    path('<int:pk>/pago/', views.payment_create, name='payment_create'),
    path('<int:pk>/deuda/', views.charge_create, name='charge_create'),
    path('<int:pk>/activar/', views.customer_toggle_active, name='customer_toggle_active'),
    path('movimiento/<int:pk>/anular/', views.entry_void, name='entry_void'),

    # API (POS)
    path('api/customers/', views.api_customers, name='api_customers'),
    path('api/customers/create/', views.api_customer_create, name='api_customer_create'),
    path('api/charge-sale/', views.api_charge_sale, name='api_charge_sale'),
]
