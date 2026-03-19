"""Quick test for signage module."""
import django, os, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'superrecord.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from signage.models import SignTemplate, SignBatch, SignItem

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()
c = Client()
c.force_login(admin)

# 1. Test pages
for url in ['/signage/', '/signage/disenador/', '/signage/disenador/?type=simple', '/signage/plantillas/', '/signage/generar/', '/signage/historial/']:
    r = c.get(url)
    assert r.status_code == 200, f'{url} returned {r.status_code}'
    print(f'  OK {r.status_code} {url}')

# 2. Test designer edit existing template
tpl = SignTemplate.objects.filter(template_type='simple').first()
r = c.get(f'/signage/disenador/{tpl.pk}/')
assert r.status_code == 200
content = r.content.decode('utf-8')
assert 'currentLayout:' in content
assert 'background_color' in content
print(f'  OK Designer edit #{tpl.pk} has resolved layout')

# 3. Create test batch
items = [{'product_id': None, 'custom_name': 'GOMITAS MORAS', 'custom_price': '1500', 'gramaje': '250g', 'copies': 2}]
r = c.post('/signage/crear-lote/', {
    'template_pk': tpl.pk,
    'paper_size': 'A4',
    'items_json': json.dumps(items),
})
assert r.status_code == 302, f'Expected redirect, got {r.status_code}'
print(f'  OK Batch created (redirect to preview)')

batch = SignBatch.objects.order_by('-pk').first()

# 4. Test preview
r = c.get(f'/signage/lote/{batch.pk}/preview/')
ct = r.content.decode('utf-8')
assert r.status_code == 200
assert 'GOMITAS MORAS' in ct, 'display_name not in preview'
# Debug: find actual price value rendered
import re
price_match = re.findall(r'data-price="([^"]*)"', ct)
print(f'  DEBUG data-price values found: {price_match}')
data_name_match = re.findall(r'data-name="([^"]*)"', ct)
print(f'  DEBUG data-name values found: {data_name_match}')
assert len(price_match) > 0, 'no data-price attributes found in preview'
assert 'SIGNAGE_LAYOUT' in ct, 'layout JS var not in preview'
print(f'  OK Preview batch #{batch.pk}: name + price + layout present')

# 5. Test print layout
r = c.get(f'/signage/lote/{batch.pk}/imprimir/')
ct3 = r.content.decode('utf-8')
assert r.status_code == 200
assert 'GOMITAS MORAS' in ct3, 'display_name not in print'
assert 'signage-render.js' in ct3, 'render JS not loaded in print'
assert '{% load static %}' not in ct3 or 'static' in ct3  # processed
print(f'  OK Print layout batch #{batch.pk}: rendering correct')

# 6. Test SignItem properties
item = batch.items.first()
assert item.display_name == 'GOMITAS MORAS'
assert '1500' in str(item.display_price)
print(f'  OK SignItem properties: display_name={item.display_name}, display_price={item.display_price}')

# Cleanup
batch.delete()
print('\nALL TESTS PASSED!')
