"""Reset signage templates to new designs."""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'superrecord.settings')
os.chdir(os.path.dirname(os.path.abspath(__file__)))
django.setup()

from signage.models import SignTemplate, ensure_default_templates

deleted = SignTemplate.objects.filter(is_default=True).delete()
created = ensure_default_templates()
templates = SignTemplate.objects.filter(is_default=True)

result_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_reset_result.txt')
with open(result_path, 'w', encoding='utf-8') as f:
    f.write(f'Deleted: {deleted}\n')
    f.write(f'Created: {created}\n')
    f.write(f'Total: {templates.count()}\n')
    for t in templates:
        f.write(f'  - {t.name} ({t.sign_type} {t.width_mm}x{t.height_mm})\n')
    f.write('DONE\n')
