"""
Libera los barcodes "atrapados" en productos y empaques previamente
desactivados (is_active=False) aplicándoles el sufijo `_deleted_{pk}`.

Antes de este refactor el soft-delete dejaba el código original en la DB,
bloqueando el alta de un producto/empaque nuevo con el mismo EAN. Esta
migración destraba todos los registros históricos sin tocar productos
activos ni datos de movimientos/lotes.
"""
from django.db import migrations


DELETED_MARKER = '_deleted_'


def release_inactive_barcodes(apps, schema_editor):
    Product = apps.get_model('stocks', 'Product')
    ProductPackaging = apps.get_model('stocks', 'ProductPackaging')

    def _suffix(value, pk):
        if not value or DELETED_MARKER in value:
            return None
        # max_length=50 — recortamos por las dudas si el original ya es largo.
        new_val = f'{value}{DELETED_MARKER}{pk}'
        return new_val[:50]

    fixed_products = 0
    for prod in Product.objects.filter(is_active=False).exclude(barcode__isnull=True).exclude(barcode=''):
        new_val = _suffix(prod.barcode, prod.pk)
        if new_val:
            prod.barcode = new_val
            prod.save(update_fields=['barcode'])
            fixed_products += 1

    fixed_pkgs = 0
    for pkg in ProductPackaging.objects.filter(is_active=False).exclude(barcode__isnull=True).exclude(barcode=''):
        new_val = _suffix(pkg.barcode, pkg.pk)
        if new_val:
            pkg.barcode = new_val
            pkg.save(update_fields=['barcode'])
            fixed_pkgs += 1

    if fixed_products or fixed_pkgs:
        print(
            f'  Released {fixed_products} product barcodes and {fixed_pkgs} '
            f'packaging barcodes from inactive records.'
        )


def restore_inactive_barcodes(apps, schema_editor):
    """Reverso: quita el sufijo `_deleted_{pk}` para volver al estado anterior.

    Se ofrece como reverse para que la migración no sea unidireccional, pero
    en la práctica casi nunca se va a usar: si se hizo rollback, los datos
    se reconstruyen desde backup.
    """
    Product = apps.get_model('stocks', 'Product')
    ProductPackaging = apps.get_model('stocks', 'ProductPackaging')

    for model in (Product, ProductPackaging):
        for obj in model.objects.filter(barcode__contains=DELETED_MARKER):
            original = obj.barcode.split(DELETED_MARKER, 1)[0]
            # Verificar que no choque con un activo antes de revertir.
            collision = model.objects.filter(
                barcode=original, is_active=True
            ).exclude(pk=obj.pk).exists()
            if not collision and original:
                obj.barcode = original
                obj.save(update_fields=['barcode'])


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0019_widen_margin_percent'),
    ]

    operations = [
        migrations.RunPython(release_inactive_barcodes, restore_inactive_barcodes),
    ]
