"""Quick smoke test for signage pages."""
import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'superrecord.settings'
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from signage.models import SignTemplate, SignBatch

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()
if not admin:
    print('ERROR: No superuser found')
    sys.exit(1)

c = Client()
c.force_login(admin)

pages = [
    ('/signage/', 'Home'),
    ('/signage/plantillas/', 'Template List'),
    ('/signage/disenador/', 'Designer New'),
    ('/signage/generar/', 'Generator'),
    ('/signage/historial/', 'History'),
]

print('=== Page Load Tests ===')
for url, name in pages:
    r = c.get(url)
    status = 'OK' if r.status_code == 200 else f'FAIL({r.status_code})'
    print(f'  {name}: {status}')

# Test designer with existing template
tpl = SignTemplate.objects.filter(is_active=True).first()
if tpl:
    r = c.get(f'/signage/disenador/{tpl.pk}/')
    s = 'OK' if r.status_code == 200 else f'FAIL({r.status_code})'
    print(f'  Designer Edit (pk={tpl.pk}): {s}')

    content = r.content.decode()
    has_config = 'SIGNAGE_DESIGNER' in content
    has_layout = 'background_color' in content
    print(f'    JS config present: {has_config}')
    print(f'    Layout data present: {has_layout}')

    # Check no JSON.parse in the served designer.js
    if 'JSON.parse(CFG.defaultLayouts)' in content:
        print('    WARNING: old JSON.parse bug still in template!')
    else:
        print('    JSON.parse bug: FIXED')

    r2 = c.get(f'/signage/generar/{tpl.pk}/')
    s2 = 'OK' if r2.status_code == 200 else f'FAIL({r2.status_code})'
    print(f'  Generator with template: {s2}')

# Test batch creation if there are products
from stocks.models import Product
products = Product.objects.filter(is_active=True)[:2]
if tpl and products.exists():
    import json
    p = products.first()
    items = [{'product_id': str(p.pk), 'custom_name': '', 'custom_price': '', 'gramaje': '100g', 'copies': 2}]
    r3 = c.post('/signage/crear-lote/', {
        'template_pk': tpl.pk,
        'paper_size': 'A4',
        'items_json': json.dumps(items),
    })
    if r3.status_code == 302:
        print(f'\n=== Batch Creation ===')
        batch = SignBatch.objects.order_by('-pk').first()
        print(f'  Batch created: #{batch.pk} ({batch.total_signs} signs)')

        # Test preview
        r4 = c.get(f'/signage/lote/{batch.pk}/preview/')
        print(f'  Preview: {"OK" if r4.status_code == 200 else "FAIL"}')
        preview_content = r4.content.decode()
        if 'data-name' in preview_content:
            print(f'    data-name attribute: present')
        if 'data-price' in preview_content:
            print(f'    data-price attribute: present')
        # Check actual values
        if p.name in preview_content:
            print(f'    Product name in HTML: YES ({p.name})')
        if str(p.sale_price) in preview_content:
            print(f'    Product price in HTML: YES ({p.sale_price})')

        # Test print layout
        r5 = c.get(f'/signage/lote/{batch.pk}/imprimir/')
        print(f'  Print layout: {"OK" if r5.status_code == 200 else "FAIL"}')
        print_content = r5.content.decode()
        if 'SIGNAGE_LAYOUT' in print_content:
            print(f'    SIGNAGE_LAYOUT config: present')
        if p.name in print_content:
            print(f'    Product name in print: YES')

        # Clean up test batch
        batch.delete()
        print(f'  Test batch cleaned up')
    else:
        print(f'  Batch creation: FAIL (status={r3.status_code})')
else:
    print('\n  (No products to test batch creation)')

print('\n=== DONE ===')
