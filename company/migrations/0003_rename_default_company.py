from django.db import migrations


def rename_default_company(apps, schema_editor):
    """Corrige el nombre por defecto heredado del fork de El Goloso."""
    Company = apps.get_model('company', 'Company')
    Company.objects.filter(name='CHE GOLOSO').update(name='Lo de Josefina')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('company', '0002_alter_branch_id_alter_company_id'),
    ]

    operations = [
        migrations.RunPython(rename_default_company, noop_reverse),
    ]
