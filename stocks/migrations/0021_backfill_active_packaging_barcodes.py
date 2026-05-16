"""Rellena el barcode de todos los ProductPackaging ACTIVOS que quedaron
con NULL/vacío, asignándoles un código interno `INT-{SKU}-{TIPO}`.

Caso reportado por el cliente: bultos cargados en versiones previas (antes
del refactor INT-{SKU}-{TIPO}) quedaron sin barcode. Aparecen en el listado
del Gestor de Empaques pero el POS no los encuentra porque la búsqueda es
exacta contra `packaging.barcode` (api_search en pos/views.py).

Esta migración los rellena masivamente para que el cliente pueda escanear/
imprimir un código y operar normalmente desde el POS. La migración 0020
liberó barcodes de inactivos; ésta cubre el lado complementario.
"""
from django.db import migrations
from django.db.models import Q


TYPE_SHORT = {'unit': 'UNI', 'display': 'DISP', 'bulk': 'BULK'}
MAX_LEN = 50  # ProductPackaging.barcode.max_length


def _build_internal(sku, pkg_type, taken):
    """Devuelve INT-{SKU}-{TIPO} o INT-{SKU}-{TIPO}-N si el base ya existe."""
    base = f'INT-{sku}-{TYPE_SHORT.get(pkg_type, "PKG")}'
    if base not in taken and len(base) <= MAX_LEN:
        return base
    n = 2
    while True:
        candidate = f'{base}-{n}'
        if candidate not in taken and len(candidate) <= MAX_LEN:
            return candidate
        n += 1


def backfill_packaging_barcodes(apps, schema_editor):
    ProductPackaging = apps.get_model('stocks', 'ProductPackaging')

    # Snapshot de barcodes ya tomados (activos+inactivos+sufijados) para
    # evitar colisiones contra el unique=True a nivel DB.
    taken = set(
        ProductPackaging.objects.exclude(barcode__isnull=True)
                                .exclude(barcode='')
                                .values_list('barcode', flat=True)
    )

    vacios = ProductPackaging.objects.filter(
        is_active=True
    ).filter(
        Q(barcode__isnull=True) | Q(barcode='')
    ).select_related('product')

    rellenados = 0
    for pkg in vacios:
        sku = (pkg.product.sku or f'PRD{pkg.product_id}').strip()
        new_code = _build_internal(sku, pkg.packaging_type, taken)
        pkg.barcode = new_code
        pkg.save(update_fields=['barcode'])
        taken.add(new_code)
        rellenados += 1

    if rellenados:
        print(f'  Rellenados {rellenados} packagings activos con código INT-.')


def noop_reverse(apps, schema_editor):
    """Reverso vacío: no tiene sentido des-rellenar (perderíamos información
    sin recuperar nada). Si se necesita rollback, restaurar desde backup."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0020_release_deleted_barcodes'),
    ]

    operations = [
        migrations.RunPython(backfill_packaging_barcodes, noop_reverse),
    ]
