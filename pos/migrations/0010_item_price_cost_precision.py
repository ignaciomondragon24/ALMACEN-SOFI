from django.db import migrations, models


class Migration(migrations.Migration):
    """Más decimales en precio y costo unitario del ítem del POS.

    En venta por peso el precio unitario es por gramo; con 2 decimales el
    subtotal (gramos × precio) se desfasaba. Solo amplía la precisión: los
    valores existentes no cambian.
    """

    dependencies = [
        ('pos', '0009_item_promotion_discount_and_group'),
    ]

    operations = [
        migrations.AlterField(
            model_name='postransactionitem',
            name='unit_price',
            field=models.DecimalField(decimal_places=6, help_text='Precio al momento de la venta', max_digits=14, verbose_name='Precio Unitario'),
        ),
        migrations.AlterField(
            model_name='postransactionitem',
            name='unit_cost',
            field=models.DecimalField(decimal_places=6, default=0, help_text='Costo del producto al momento de la venta (para cálculo de ganancia)', max_digits=14, verbose_name='Costo Unitario'),
        ),
    ]
