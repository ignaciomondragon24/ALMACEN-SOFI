"""
Signage URLs
"""
from django.urls import path
from . import views

app_name = 'signage'

urlpatterns = [
    path('', views.signage_home, name='home'),
    path('generate/', views.generate_sign, name='generate'),
    path('preview/<int:pk>/', views.preview_sign, name='preview'),
    path('download/<int:pk>/', views.download_sign, name='download'),
    path('quick/<int:promo_id>/', views.quick_promo_sign, name='quick_promo_sign'),
    path('history/', views.history, name='history'),
    path('templates/', views.template_list, name='template_list'),
]
