"""
Libera de nuevo los códigos de barras retenidos por productos/empaques
inactivos.

Destildar "Activo" en el formulario de producto (o en el admin) desactivaba
el registro sin liberar el código: el buscador lo ignoraba ("no existe") pero
la BD lo seguía considerando único, así que crearlo de nuevo fallaba con
"ya existe". Desde este cambio `save()` lo libera solo; esta migración
destraba los que ya quedaron así. Idempotente.
"""
from django.db import migrations

DELETED_MARKER = '_deleted_'


def _suffix(value, pk):
    if not value or DELETED_MARKER in value:
        return None
    return f'{value}{DELETED_MARKER}{pk}'[:50]


def release(apps, schema_editor):
    Product = apps.get_model('stocks', 'Product')
    ProductPackaging = apps.get_model('stocks', 'ProductPackaging')

    # Empaques activos de productos inactivos: se desactivan.
    ProductPackaging.objects.filter(
        is_active=True, product__is_active=False
    ).update(is_active=False)

    for model in (Product, ProductPackaging):
        qs = (model.objects.filter(is_active=False)
              .exclude(barcode__isnull=True).exclude(barcode=''))
        for obj in qs:
            new_val = _suffix(obj.barcode, obj.pk)
            if new_val:
                model.objects.filter(pk=obj.pk).update(barcode=new_val)


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0029_alter_product_min_stock'),
    ]

    operations = [
        migrations.RunPython(release, migrations.RunPython.noop),
    ]
