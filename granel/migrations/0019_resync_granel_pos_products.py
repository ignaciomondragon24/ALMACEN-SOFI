from django.db import migrations


def resync_pos_products(apps, schema_editor):
    """Re-sincroniza el producto del POS de cada caramelera con sus datos reales.

    Hasta ahora, si una caramelera se creaba autorizando una pieza de depósito
    que ya tenía stock, el producto del POS quedaba con stock 0 y costo 0 aunque
    la caramelera sí tuviera mercadería (se copiaba una copia vieja en memoria).
    Esto corrige lo ya cargado; no toca la caramelera ni sus ventas.
    """
    Caramelera = apps.get_model('granel', 'Caramelera')
    Product = apps.get_model('stocks', 'Product')
    for caramelera in Caramelera.objects.all():
        Product.objects.filter(is_granel=True, granel_caramelera_id=caramelera.pk).update(
            current_stock=caramelera.stock_gramos_actual,
            weighted_avg_cost_per_gram=caramelera.costo_ponderado_gramo,
            sale_price=caramelera.precio_100g,
            sale_price_250g=caramelera.precio_cuarto,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('granel', '0018_alter_caramelera_productos_autorizados'),
        ('stocks', '0023_stockbatch_expiration_date_and_more'),
    ]

    operations = [
        migrations.RunPython(resync_pos_products, migrations.RunPython.noop),
    ]
