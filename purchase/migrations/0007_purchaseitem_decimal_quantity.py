from decimal import Decimal
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    """La cantidad de una orden de compra admite decimales (kilos en productos por peso).

    Los valores existentes no cambian (5 pasa a 5.000).
    """

    dependencies = [
        ('purchase', '0006_supplier_order_day_supplierproduct_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='purchaseitem',
            name='quantity',
            field=models.DecimalField(decimal_places=3, help_text='Cantidad expresada en la unidad del empaque seleccionado (o unidades base si no hay empaque). En productos por peso son kilos.', max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.001'))], verbose_name='Cantidad'),
        ),
        migrations.AlterField(
            model_name='purchaseitem',
            name='received_quantity',
            field=models.DecimalField(decimal_places=3, default=Decimal('0'), max_digits=10, verbose_name='Cantidad Recibida'),
        ),
    ]
