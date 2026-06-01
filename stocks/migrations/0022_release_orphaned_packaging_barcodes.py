"""Libera barcodes de packagings activos cuyos productos están inactivos.

Caso: un producto fue soft-deleted (is_active=False) pero el soft-delete
no cascadeó a sus empaques. El empaque queda is_active=True con su barcode
original, bloqueando que otro producto lo use y confundiendo búsquedas.

Ejemplo concreto: "mentias felfort 30u." (inactivo) tenía el packaging
"Bulto x 29" (id=25, is_active=True, barcode="7790206008308"), impidiendo
registrar ese barcode en el producto correcto.

Esta migración aplica el mismo sufijo `_deleted_{pk}` que usa
ProductPackaging.delete() en esos empaques huérfanos.
"""
from django.db import migrations

DELETED_MARKER = '_deleted_'


def release_orphaned_packagings(apps, schema_editor):
    ProductPackaging = apps.get_model('stocks', 'ProductPackaging')

    orphans = ProductPackaging.objects.filter(
        is_active=True,
        product__is_active=False,
    ).exclude(
        barcode__isnull=True,
    ).exclude(
        barcode__contains=DELETED_MARKER,
    )

    count = 0
    for pkg in orphans:
        pkg.is_active = False
        if pkg.barcode:
            pkg.barcode = f'{pkg.barcode}{DELETED_MARKER}{pkg.pk}'
        pkg.save(update_fields=['is_active', 'barcode'])
        count += 1

    if count:
        print(f'  Liberados {count} packagings huérfanos (producto inactivo).')


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0021_backfill_active_packaging_barcodes'),
    ]

    operations = [
        migrations.RunPython(release_orphaned_packagings, noop_reverse),
    ]
