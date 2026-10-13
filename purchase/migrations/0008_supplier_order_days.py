from django.db import migrations, models


def copiar_dia(apps, schema_editor):
    Supplier = apps.get_model('purchase', 'Supplier')
    for s in Supplier.objects.exclude(order_day=''):
        s.order_days = s.order_day
        s.save(update_fields=['order_days'])


def restaurar_dia(apps, schema_editor):
    Supplier = apps.get_model('purchase', 'Supplier')
    for s in Supplier.objects.exclude(order_days=''):
        s.order_day = s.order_days.split(',')[0]
        s.save(update_fields=['order_day'])


class Migration(migrations.Migration):

    dependencies = [
        ('purchase', '0007_purchaseitem_decimal_quantity'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplier',
            name='order_days',
            field=models.CharField(blank=True, help_text='Días habituales en que se le hacen pedidos a este proveedor (para los avisos de pedido).', max_length=40, verbose_name='Días de Pedido'),
        ),
        migrations.RunPython(copiar_dia, restaurar_dia),
        migrations.RemoveField(
            model_name='supplier',
            name='order_day',
        ),
    ]
