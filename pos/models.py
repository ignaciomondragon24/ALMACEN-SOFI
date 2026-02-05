"""
POS Models - Point of Sale
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone


class POSSession(models.Model):
    """POS Session linked to a cash shift."""
    
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('closed', 'Cerrado'),
    ]
    
    cash_shift = models.ForeignKey(
        'cashregister.CashShift',
        on_delete=models.PROTECT,
        related_name='pos_sessions',
        verbose_name='Turno de Caja'
    )
    opened_at = models.DateTimeField(
        'Apertura',
        auto_now_add=True
    )
    closed_at = models.DateTimeField(
        'Cierre',
        null=True,
        blank=True
    )
    status = models.CharField(
        'Estado',
        max_length=20,
        choices=STATUS_CHOICES,
        default='active'
    )
    
    class Meta:
        verbose_name = 'Sesión POS'
        verbose_name_plural = 'Sesiones POS'
        ordering = ['-opened_at']
    
    def __str__(self):
        return f'Sesión {self.pk} - {self.cash_shift}'
    
    @property
    def total_transactions(self):
        return self.transactions.filter(status='completed').count()
    
    @property
    def total_amount(self):
        from django.db.models import Sum
        result = self.transactions.filter(status='completed').aggregate(
            total=Sum('total')
        )
        return result['total'] or Decimal('0.00')


class POSTransaction(models.Model):
    """POS Transaction (sale)."""
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('completed', 'Completada'),
        ('cancelled', 'Cancelada'),
        ('suspended', 'Suspendida'),
    ]
    
    TRANSACTION_TYPE_CHOICES = [
        ('sale', 'Venta'),
        ('cost_sale', 'Venta al Costo'),
        ('internal_consumption', 'Consumo Interno'),
    ]
    
    session = models.ForeignKey(
        POSSession,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name='Sesión'
    )
    ticket_number = models.CharField(
        'Número de Ticket',
        max_length=50,
        unique=True,
        help_text='Formato: CAJA-XX-YYYYMMDD-NNNN'
    )
    status = models.CharField(
        'Estado',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    transaction_type = models.CharField(
        'Tipo de Transacción',
        max_length=30,
        choices=TRANSACTION_TYPE_CHOICES,
        default='sale'
    )
    
    # Totals
    subtotal = models.DecimalField(
        'Subtotal',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    discount_total = models.DecimalField(
        'Total Descuentos',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax_total = models.DecimalField(
        'Total Impuestos',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total = models.DecimalField(
        'Total',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    items_count = models.PositiveIntegerField(
        'Cantidad de Ítems',
        default=0
    )
    
    # Payment info
    amount_paid = models.DecimalField(
        'Monto Pagado',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    change_given = models.DecimalField(
        'Vuelto',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        'Creación',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        'Actualización',
        auto_now=True
    )
    completed_at = models.DateTimeField(
        'Completada',
        null=True,
        blank=True
    )
    cancelled_at = models.DateTimeField(
        'Cancelada',
        null=True,
        blank=True
    )
    suspended_at = models.DateTimeField(
        'Suspendida',
        null=True,
        blank=True
    )
    
    notes = models.TextField(
        'Notas',
        blank=True
    )
    
    class Meta:
        verbose_name = 'Transacción POS'
        verbose_name_plural = 'Transacciones POS'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['ticket_number']),
            models.Index(fields=['status']),
            models.Index(fields=['completed_at']),
        ]
    
    def __str__(self):
        return f'{self.ticket_number} - ${self.total}'
    
    def calculate_totals(self):
        """Recalculate transaction totals from items."""
        from django.db.models import Sum, F
        
        result = self.items.aggregate(
            subtotal=Sum(F('unit_price') * F('quantity')),
            discount=Sum('discount'),
            count=Sum('quantity')
        )
        
        self.subtotal = result['subtotal'] or Decimal('0.00')
        self.discount_total = result['discount'] or Decimal('0.00')
        self.total = self.subtotal - self.discount_total + self.tax_total
        self.items_count = int(result['count'] or 0)
        self.save()


class POSTransactionItem(models.Model):
    """Item in a POS transaction."""
    
    transaction = models.ForeignKey(
        POSTransaction,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Transacción'
    )
    product = models.ForeignKey(
        'stocks.Product',
        on_delete=models.PROTECT,
        related_name='pos_items',
        verbose_name='Producto'
    )
    quantity = models.PositiveIntegerField(
        'Cantidad',
        default=1,
        validators=[MinValueValidator(1)]
    )
    unit_price = models.DecimalField(
        'Precio Unitario',
        max_digits=10,
        decimal_places=2,
        help_text='Precio al momento de la venta'
    )
    discount = models.DecimalField(
        'Descuento',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    subtotal = models.DecimalField(
        'Subtotal',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    
    # Promotion info
    promotion = models.ForeignKey(
        'promotions.Promotion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transaction_items',
        verbose_name='Promoción'
    )
    promotion_name = models.CharField(
        'Nombre Promoción',
        max_length=200,
        blank=True,
        help_text='Guardado para histórico'
    )
    
    class Meta:
        verbose_name = 'Ítem de Transacción'
        verbose_name_plural = 'Ítems de Transacción'
        ordering = ['id']
    
    def __str__(self):
        return f'{self.product.name} x {self.quantity}'
    
    def save(self, *args, **kwargs):
        # Calculate subtotal
        self.subtotal = (self.unit_price * self.quantity) - self.discount
        super().save(*args, **kwargs)


class POSPayment(models.Model):
    """Payment for a POS transaction."""
    
    transaction = models.ForeignKey(
        POSTransaction,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Transacción'
    )
    payment_method = models.ForeignKey(
        'cashregister.PaymentMethod',
        on_delete=models.PROTECT,
        related_name='pos_payments',
        verbose_name='Método de Pago'
    )
    amount = models.DecimalField(
        'Monto',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    reference = models.CharField(
        'Referencia',
        max_length=100,
        blank=True,
        help_text='Últimos 4 dígitos de tarjeta, etc.'
    )
    created_at = models.DateTimeField(
        'Fecha',
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = 'Pago POS'
        verbose_name_plural = 'Pagos POS'
        ordering = ['created_at']
    
    def __str__(self):
        return f'{self.payment_method.name} - ${self.amount}'


class QuickAccessButton(models.Model):
    """Quick access button for POS."""
    
    product = models.OneToOneField(
        'stocks.Product',
        on_delete=models.CASCADE,
        related_name='quick_button',
        verbose_name='Producto'
    )
    name = models.CharField(
        'Nombre en Botón',
        max_length=50,
        blank=True,
        help_text='Nombre corto para el botón. Si vacío, usa el nombre del producto.'
    )
    color = models.CharField(
        'Color',
        max_length=7,
        default='#3498db',
        help_text='Código hexadecimal'
    )
    icon = models.CharField(
        'Icono',
        max_length=50,
        default='fa-box',
        help_text='Clase Font Awesome'
    )
    position = models.PositiveIntegerField(
        'Posición',
        default=0
    )
    is_active = models.BooleanField(
        'Activo',
        default=True
    )
    
    class Meta:
        verbose_name = 'Botón de Acceso Rápido'
        verbose_name_plural = 'Botones de Acceso Rápido'
        ordering = ['position', 'product__name']
    
    def __str__(self):
        return self.display_name
    
    @property
    def display_name(self):
        return self.name or self.product.name
