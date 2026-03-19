"""
Signage URLs - Diseñador Visual de Carteles
"""
from django.urls import path
from . import views

app_name = 'signage'

urlpatterns = [
    # Home / Dashboard
    path('', views.signage_home, name='home'),

    # Template management
    path('plantillas/', views.template_list, name='template_list'),
    path('diseñador/', views.designer, name='designer_new'),
    path('diseñador/<int:pk>/', views.designer, name='designer_edit'),
    path('plantilla/<int:pk>/eliminar/', views.template_delete, name='template_delete'),

    # API (AJAX)
    path('api/template-defaults/', views.api_template_defaults, name='api_template_defaults'),

    # Generator
    path('generar/', views.generator, name='generator'),
    path('generar/<int:template_pk>/', views.generator, name='generator_with_template'),
    path('crear-lote/', views.create_batch, name='create_batch'),

    # Preview & Print
    path('lote/<int:pk>/preview/', views.preview_batch, name='preview_batch'),
    path('lote/<int:pk>/imprimir/', views.print_layout, name='print_layout'),

    # History
    path('historial/', views.history, name='history'),
]
