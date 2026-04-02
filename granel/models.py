"""
Granel Models - Bulk-to-retail candy system, stock batches, shrinkage audits.
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal

# StockBatch ahora vive en stocks.models — re-exportamos para compatibilidad
from stocks.models import StockBatch  # noqa: F401


class BulkToGranelTransfer(models.Model):
    """Log de cada apertura de bolsa para rellenar la caramelera."""
    bulk_product = models.ForeignKey(
        'stocks.Product',
        on_delete=models.PROTECT,
        related_name='granel_transfers_out',
        verbose_name='Producto Bulto (origen)'
    )
    granel_product = models.ForeignKey(
        'stocks.Product',
        on_delete=models.PROTECT,
        related_name='granel_transfers_in',
        verbose_name='Producto Granel (destino)'
    )
    source_batch = models.ForeignKey(
        StockBatch,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='granel_transfers',
        verbose_name='Lote Origen'
    )
    grams_transferred = models.DecimalField(
        'Gramos Transferidos',
        max_digits=10,
        decimal_places=2
    )
    bulk_cost_per_gram = models.DecimalField(
        'Costo por Gramo (bulto)',
        max_digits=12,
        decimal_places=4
    )
    granel_stock_before = models.DecimalField(
        'Stock Granel Antes (g)',
        max_digits=12,
        decimal_places=2
    )
    granel_weighted_cost_before = models.DecimalField(
        'Costo Ponderado Antes ($/g)',
        max_digits=12,
        decimal_places=4
    )
    granel_stock_after = models.DecimalField(
        'Stock Granel Después (g)',
        max_digits=12,
        decimal_places=2
    )
    granel_weighted_cost_after = models.DecimalField(
        'Costo Ponderado Después ($/g)',
        max_digits=12,
        decimal_places=4
    )
    transferred_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='granel_transfers',
        verbose_name='Transferido por'
    )
    transferred_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField('Notas', blank=True)

    class Meta:
        verbose_name = 'Transferencia Bulto a Granel'
        verbose_name_plural = 'Transferencias Bulto a Granel'
        ordering = ['-transferred_at']

    def __str__(self):
        return (f'{self.bulk_product.name} -> {self.granel_product.name} '
                f'({self.grams_transferred}g)')


class CarameleraComponent(models.Model):
    """
    Define qué productos bulto componen una caramelera.
    Permite el botón "Abrir Paquete" desde el dashboard sin tener que
    seleccionar origen y destino cada vez.
    """
    caramelera = models.ForeignKey(
        'stocks.Product',
        on_delete=models.CASCADE,
        related_name='components',
        limit_choices_to={'is_granel': True},
        verbose_name='Caramelera',
    )
    bulk_product = models.ForeignKey(
        'stocks.Product',
        on_delete=models.CASCADE,
        related_name='used_in_carameleras',
        verbose_name='Producto Bulto (gomitas/caramelos)',
    )
    proportion_grams = models.DecimalField(
        'Gramos en receta',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0')
    )
    notes = models.CharField('Notas', max_length=200, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Componente de Caramelera'
        verbose_name_plural = 'Componentes de Caramelera'
        unique_together = ('caramelera', 'bulk_product')
        ordering = ['bulk_product__name']

    def __str__(self):
        return f'{self.bulk_product.name} → {self.caramelera.name}'


class ShrinkageAudit(models.Model):
    """Auditoría de mermas por pesaje."""
    REASON_CHOICES = [
        ('picoteo', 'Picoteo/Degustación'),
        ('humedad', 'Humedad/Evaporación'),
        ('pesaje', 'Error de Pesaje'),
        ('otro', 'Otro'),
    ]

    granel_product = models.ForeignKey(
        'stocks.Product',
        on_delete=models.PROTECT,
        related_name='shrinkage_audits',
        verbose_name='Producto Granel'
    )
    theoretical_grams = models.DecimalField(
        'Stock Teórico (g)',
        max_digits=12,
        decimal_places=2
    )
    actual_grams = models.DecimalField(
        'Peso Real (g)',
        max_digits=12,
        decimal_places=2
    )
    shrinkage_grams = models.DecimalField(
        'Diferencia (g)',
        max_digits=12,
        decimal_places=2,
        help_text='Positivo = sobrante, negativo = merma'
    )
    shrinkage_percent = models.DecimalField(
        'Merma %',
        max_digits=5,
        decimal_places=2
    )
    reason = models.CharField(
        'Motivo',
        max_length=20,
        choices=REASON_CHOICES,
        default='otro'
    )
    notes = models.TextField('Notas', blank=True)
    stock_adjusted = models.BooleanField(
        'Stock Ajustado',
        default=False,
        help_text='Si se aplicó el ajuste al stock del producto granel'
    )
    audited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='shrinkage_audits',
        verbose_name='Auditado por'
    )
    audited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Auditoría de Merma'
        verbose_name_plural = 'Auditorías de Merma'
        ordering = ['-audited_at']

    def __str__(self):
        return (f'Merma {self.granel_product.name}: '
                f'{self.shrinkage_grams}g ({self.shrinkage_percent}%)')
