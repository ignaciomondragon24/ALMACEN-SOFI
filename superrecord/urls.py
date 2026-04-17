"""
URL Configuration for CHE GOLOSO Supermarket Management System.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse


def health_check(request):
    from django.db import connection
    from django.contrib.staticfiles.storage import staticfiles_storage
    from django.conf import settings as dj_settings
    import os
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        storage_cls = f"{staticfiles_storage.__class__.__module__}.{staticfiles_storage.__class__.__name__}"
        test_url = staticfiles_storage.url('js/main.js')
        hashed_files = getattr(staticfiles_storage, 'hashed_files', None)
        manifest_path = os.path.join(dj_settings.STATIC_ROOT, 'staticfiles.json')
        manifest_exists = os.path.exists(manifest_path)
        mro = [c.__name__ for c in staticfiles_storage.__class__.__mro__]
        hashed_keys = list(hashed_files.keys())[:3] if hashed_files else []
        js_main_in_hashed = 'js/main.js' in (hashed_files or {})
        js_keys_sample = [k for k in (hashed_files or {}).keys() if k.startswith('js/')][:10]
        pos_dark_in_hashed = 'css/pos-dark.css' in (hashed_files or {})
        manifest_raw = None
        try:
            with open(manifest_path, 'r') as mf:
                import json as _json
                manifest_raw = _json.load(mf)
                manifest_js_main = manifest_raw.get('paths', {}).get('js/main.js')
        except Exception as me:
            manifest_js_main = f'err: {me}'
        return JsonResponse({
            'status': 'ok',
            'db': 'ok',
            'staticfiles_storage_setting': getattr(dj_settings, 'STATICFILES_STORAGE', None),
            'staticfiles_storage_class': storage_cls,
            'storage_mro': mro,
            'main_js_url': test_url,
            'hashed_files_count': len(hashed_files) if hashed_files is not None else None,
            'hashed_sample_keys': hashed_keys,
            'manifest_path': str(manifest_path),
            'manifest_exists': manifest_exists,
            'has_load_manifest': hasattr(staticfiles_storage, 'load_manifest'),
            'js_main_in_hashed': js_main_in_hashed,
            'js_keys_sample': js_keys_sample,
            'pos_dark_in_hashed': pos_dark_in_hashed,
            'manifest_js_main': manifest_js_main,
            'manifest_paths_count': len(manifest_raw.get('paths', {})) if manifest_raw else 0,
            'DEBUG': dj_settings.DEBUG,
            'DEBUG_env': os.getenv('DEBUG', '<unset>'),
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'db': str(e)}, status=503)


urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('pos/', include('pos.urls')),
    path('cashregister/', include('cashregister.urls')),
    path('stocks/', include('stocks.urls')),
    path('promotions/', include('promotions.urls')),
    path('purchase/', include('purchase.urls')),
    path('expenses/', include('expenses.urls')),
    path('sales/', include('sales.urls')),
    path('company/', include('company.urls')),
    path('mercadopago/', include('mercadopago.urls')),
    path('assistant/', include('assistant.urls')),
    path('signage/', include('signage.urls')),
    path('granel/', include('granel.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Admin site customization
admin.site.site_header = 'CHE GOLOSO - Administración'
admin.site.site_title = 'CHE GOLOSO Admin'
admin.site.index_title = 'Panel de Administración'
