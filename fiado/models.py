"""
Fiado - cuenta corriente de clientes.

El saldo de un cliente NO se guarda: se calcula como cargos - pagos (sin los
movimientos anulados). Lo fiado no es una venta del día y lo que el cliente
paga después tampoco: por eso viven acá y no en POSPayment/ventas.
"""
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q, Sum


class Customer(models.Model):
    """Cliente con cuenta de fiado."""

    name = models.CharField('Nombre', max_length=120)
    phone = models.CharField('Teléfono', max_length=40, blank=True)
    notes = models.TextField('Notas', blank=True)
    is_active = models.BooleanField('Activo', default=True)
    created_at = models.DateTimeField('Alta', auto_now_add=True)

    class Meta:
        verbose_name = 'Cliente de fiado'
        verbose_name_plural = 'Clientes de fiado'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def balance(self):
        """Lo que el cliente debe hoy (cargos - pagos, sin anulados)."""
        totals = self.entries.filter(voided_at__isnull=True).aggregate(
            charges=Sum('amount', filter=Q(entry_type=FiadoEntry.CHARGE)),
            payments=Sum('amount', filter=Q(entry_type=FiadoEntry.PAYMENT)),
        )
        return (totals['charges'] or Decimal('0.00')) - (totals['payments'] or Decimal('0.00'))


class FiadoEntry(models.Model):
    """Movimiento de la cuenta: un cargo (el cliente se lleva algo) o un pago."""

    CHARGE = 'charge'
    PAYMENT = 'payment'
    TYPE_CHOICES = [
        (CHARGE, 'Fiado'),
        (PAYMENT, 'Pago'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name='entries',
        verbose_name='Cliente',
    )
    entry_type = models.CharField('Tipo', max_length=10, choices=TYPE_CHOICES)
    amount = models.DecimalField(
        'Monto',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    note = models.CharField('Nota', max_length=200, blank=True)

    # Cargo que viene de una venta del POS (null = deuda cargada a mano).
    pos_transaction = models.ForeignKey(
        'pos.POSTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fiado_entries',
        verbose_name='Venta',
    )
    ticket_number = models.CharField('Ticket', max_length=50, blank=True)

    # Pago: cómo y en qué turno entró la plata.
    payment_method = models.ForeignKey(
        'cashregister.PaymentMethod',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='fiado_entries',
        verbose_name='Método de pago',
    )
    cash_shift = models.ForeignKey(
        'cashregister.CashShift',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fiado_entries',
        verbose_name='Turno',
    )
    cash_movement = models.OneToOneField(
        'cashregister.CashMovement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fiado_entry',
        verbose_name='Movimiento de caja',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='fiado_entries',
        verbose_name='Registrado por',
    )
    created_at = models.DateTimeField('Fecha', auto_now_add=True)

    voided_at = models.DateTimeField('Anulado', null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='fiado_voids',
        verbose_name='Anulado por',
    )
    void_reason = models.CharField('Motivo de anulación', max_length=200, blank=True)

    class Meta:
        verbose_name = 'Movimiento de fiado'
        verbose_name_plural = 'Movimientos de fiado'
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.get_entry_type_display()} ${self.amount} - {self.customer}'

    @property
    def is_voided(self):
        return self.voided_at is not None

    @property
    def can_void(self):
        """Las ventas con productos no se anulan desde acá (el stock ya salió)."""
        if self.is_voided:
            return False
        if self.entry_type == self.CHARGE and self.pos_transaction_id:
            return False
        return True
