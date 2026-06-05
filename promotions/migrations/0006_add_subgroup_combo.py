from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('promotions', '0005_promotion_applies_to_packaging_type'),
        ('stocks', '0022_release_orphaned_packaging_barcodes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='promotion',
            name='promo_type',
            field=models.CharField(
                choices=[
                    ('nxm', 'NxM (Ej: 2x1, 3x2)'),
                    ('nx_fixed_price', 'N por Precio Fijo (Ej: 2x$500, 3x$1000)'),
                    ('quantity_discount', 'Descuento por Cantidad'),
                    ('combo', 'Combo'),
                    ('second_unit', 'Segunda Unidad con Descuento'),
                    ('simple_discount', 'Descuento Porcentual'),
                    ('subgroup_combo', 'Combo por Subgrupos (Ej: 2 Lactal + 1 Hamburguesa)'),
                ],
                max_length=30,
                verbose_name='Tipo de Promoción',
            ),
        ),
        migrations.CreateModel(
            name='PromotionSubgroup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('slot', models.CharField(
                    choices=[('a', 'Grupo A'), ('b', 'Grupo B')],
                    max_length=1,
                    verbose_name='Grupo',
                )),
                ('quantity_required', models.PositiveIntegerField(default=1, verbose_name='Cantidad requerida')),
                ('promotion', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='subgroups',
                    to='promotions.promotion',
                    verbose_name='Promoción',
                )),
                ('products', models.ManyToManyField(
                    blank=True,
                    to='stocks.product',
                    verbose_name='Productos del grupo',
                )),
            ],
            options={
                'verbose_name': 'Subgrupo de Promoción',
                'verbose_name_plural': 'Subgrupos de Promoción',
                'unique_together': {('promotion', 'slot')},
            },
        ),
    ]
