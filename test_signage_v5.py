"""Quick functional test for signage v5 rewrite."""
import os, sys, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'superrecord.settings')

import django
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from signage.models import SignTemplate, SignBatch

User = get_user_model()
admin = User.objects.filter(is_superuser=True).first()
if not admin:
    print("ERROR: No superuser found")
    sys.exit(1)

c = Client()
c.force_login(admin)
ok = 0
fail = 0

def check(desc, cond):
    global ok, fail
    if cond:
        ok += 1
        print(f"  OK  {desc}")
    else:
        fail += 1
        print(f"  FAIL {desc}")

print("=== Signage v5 Tests ===")

# 1. Home page
r = c.get('/signage/')
check("Home page loads", r.status_code == 200)

# 2. Template list
r = c.get('/signage/plantillas/')
check("Template list loads", r.status_code == 200)

# 3. Designer (new)
r = c.get('/signage/disenador/')
check("Designer (new) loads", r.status_code == 200)
ct = r.content.decode()
check("Designer loads signage-render.js", 'signage-render.js' in ct)
check("Designer loads signage-designer.js", 'signage-designer.js' in ct)
check("Designer has SIGNAGE_DESIGNER config", 'SIGNAGE_DESIGNER' in ct)

# 4. Designer with type param
r = c.get('/signage/disenador/?type=promotional')
check("Designer ?type=promotional loads", r.status_code == 200)

# 5. Get existing template
tpl = SignTemplate.objects.first()
if tpl:
    r = c.get(f'/signage/disenador/{tpl.pk}/')
    check(f"Designer edit (pk={tpl.pk}) loads", r.status_code == 200)

# 6. Generator
r = c.get('/signage/generar/')
check("Generator loads", r.status_code == 200)

# 7. Create a test batch and check preview + print
tpl = SignTemplate.objects.filter(template_type='simple').first()
if tpl:
    items = [{'product_id': None, 'custom_name': 'TEST PROD', 'custom_price': '999', 'gramaje': '100g', 'copies': 2}]
    r = c.post('/signage/crear-lote/', {
        'template_pk': tpl.pk,
        'paper_size': 'A4',
        'items_json': json.dumps(items),
    })
    check("Create batch redirects (302)", r.status_code == 302)

    batch = SignBatch.objects.order_by('-pk').first()
    if batch:
        # Preview
        r = c.get(f'/signage/lote/{batch.pk}/preview/')
        check("Preview loads", r.status_code == 200)
        ct = r.content.decode()
        check("Preview has sign data", 'TEST PROD' in ct)
        check("Preview has unit:mm", "unit: 'mm'" in ct or '{unit: ' in ct)
        check("Preview loads render.js", 'signage-render.js' in ct)

        # Print
        r = c.get(f'/signage/lote/{batch.pk}/imprimir/')
        check("Print loads", r.status_code == 200)
        ct2 = r.content.decode()
        check("Print has sign data", 'TEST PROD' in ct2)
        check("Print has sign-fit CSS", '.sign-fit' in ct2)
        check("Print loads render.js", 'signage-render.js' in ct2)
        check("Print passes unit mm", "unit: 'mm'" in ct2 or '{unit: ' in ct2)

        # Cleanup
        batch.delete()
        print("  Batch cleaned up")

# 8. API defaults
r = c.get('/signage/api/template-defaults/')
check("API defaults loads", r.status_code == 200)

# 9. History
r = c.get('/signage/historial/')
check("History loads", r.status_code == 200)

print(f"\n=== Results: {ok} passed, {fail} failed ===")
if fail > 0:
    sys.exit(1)
else:
    print("ALL TESTS PASSED")
