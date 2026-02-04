"""
URL Configuration for CHE GOLOSO Supermarket Management System.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('pos/', include('pos.urls')),
    path('cashregister/', include('cashregister.urls')),
    path('stocks/', include('stocks.urls')),
    path('promotions/', include('promotions.urls')),
    path('signage/', include('signage.urls')),
    path('purchase/', include('purchase.urls')),
    path('expenses/', include('expenses.urls')),
    path('sales/', include('sales.urls')),
    path('company/', include('company.urls')),
    path('mercadopago/', include('mercadopago.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = 'CHE GOLOSO - Administración'
admin.site.site_title = 'CHE GOLOSO Admin'
admin.site.index_title = 'Panel de Administración'
