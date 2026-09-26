"""
Fase 3 del rediseño de venta por peso — Migración B (irreversible).

Borra las 4 columnas del sistema VIEJO de venta por peso, ya sin uso desde
que la Migración A (0025) copió sus datos reales al sistema nuevo y
desvinculó la FK. Antes de este deploy se sacaron todas las referencias a
estos campos del código de `stocks`, `pos`, `mercadopago`, `purchase` y del
sync de `Caramelera.save()` en `granel` — ver el commit y el plan
`sharded-honking-quilt.md`.

No toca la app `granel`: sus modelos, migraciones y datos (las 8 Carameleras
originales, ahora huérfanas) quedan intactos en la base, como historial.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('stocks', '0025_migrar_carameleras_y_depositos'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='granel_caramelera',
        ),
        migrations.RemoveField(
            model_name='product',
            name='es_deposito_caramelera',
        ),
        migrations.RemoveField(
            model_name='product',
            name='granel_price_weight_grams',
        ),
        migrations.RemoveField(
            model_name='product',
            name='weighted_avg_cost_per_gram',
        ),
    ]
