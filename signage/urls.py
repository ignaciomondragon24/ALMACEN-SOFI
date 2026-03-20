from django.urls import path
from . import views

app_name = 'signage'

urlpatterns = [
    path('', views.template_list, name='template_list'),
    path('nueva/', views.template_create, name='template_create'),
    path('disenador/<int:pk>/', views.designer, name='designer'),
    path('eliminar/<int:pk>/', views.template_delete, name='template_delete'),
    path('generar/<int:pk>/', views.generate, name='generate'),
    path('lotes/', views.batch_list, name='batch_list'),
    path('imprimir/', views.print_view, name='print_view'),

    # API endpoints (AJAX)
    path('api/save-layout/<int:pk>/', views.save_layout, name='save_layout'),
    path('api/product-data/', views.api_product_data, name='api_product_data'),
    path('api/save-batch/', views.save_batch, name='save_batch'),
]
