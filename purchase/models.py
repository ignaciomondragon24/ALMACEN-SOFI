"""
Purchase Models - Suppliers and Purchases
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal


class Supplier(models.Model):
    """Supplier model."""

    WEEKDAY_CHOICES = [
        ('mon', 'Lunes'),
        ('tue', 'Martes'),
        ('wed', 'Miércoles'),
        ('thu', 'Jueves'),
        ('fri', 'Viernes'),
        ('sat', 'Sábado'),
        ('sun', 'Domingo'),
    ]
    # Índice de Python (date.weekday(): lunes=0) -> código del choice.
    _WEEKDAY_INDEX = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

    name = models.CharField(
        'Nombre',
        max_length=200
    )
    order_day = models.CharField(
        'Día de Pedido',
        max_length=3,
        choices=WEEKDAY_CHOICES,
        blank=True,
        help_text='Día habitual en que se le hacen pedidos a este proveedor (para el aviso de pedido sugerido).'
    )
    contact_name = models.CharField(
        'Contacto',
        max_length=200,
        blank=True
    )
    phone = models.CharField(
        'Teléfono',
        max_length=50,
        blank=True
    )
    email = models.EmailField(
        'Email',
        blank=True
    )
    address = models.TextField(
        'Dirección',
        blank=True
    )
    cuit = models.CharField(
        'CUIT',
        max_length=20,
        blank=True
    )
    notes = models.TextField(
        'Notas',
        blank=True
    )
    is_active = models.BooleanField(
        'Activo',
        default=True
    )
    created_at = models.DateTimeField(
        'Fecha de Creación',
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['name']

    def __str__(self):
        return self.name

    @classmethod
    def weekday_code(cls, date):
        """Convierte una fecha en el código de día usado por order_day."""
        return cls._WEEKDAY_INDEX[date.weekday()]

    @property
    def is_order_day_today(self):
        from django.utils import timezone
        return bool(self.order_day) and self.order_day == self.weekday_code(timezone.now().date())


class SupplierProduct(models.Model):
    """
    Vincula un producto con un proveedor habitual, con el precio al que se lo compra.
    Usado para generar el aviso/orden de pedido sugerido cuando el stock está bajo.
    """

    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.CASCADE,
        related_name='supplier_products',
        verbose_name='Proveedor'
    )
    product = models.ForeignKey(
        'stocks.Product',
        on_delete=models.CASCADE,
        related_name='supplier_links',
        verbose_name='Producto'
    )
    cost_price = models.DecimalField(
        'Precio de Compra',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Precio al que este proveedor vende el producto.'
    )
    notes = models.CharField(
        'Notas',
        max_length=200,
        blank=True
    )
    is_active = models.BooleanField(
        'Activo',
        default=True
    )
    created_at = models.DateTimeField(
        'Fecha de Creación',
        auto_now_add=True
    )

    class Meta:
        verbose_name = 'Producto de Proveedor'
        verbose_name_plural = 'Productos de Proveedor'
        ordering = ['supplier__name', 'product__name']
        constraints = [
            models.UniqueConstraint(fields=['supplier', 'product'], name='unique_supplier_product')
        ]

    def __str__(self):
        return f'{self.product.name} — {self.supplier.name}'

    @property
    def por_peso(self):
        return bool(self.product.is_granel)

    @property
    def precio_texto(self):
        """Precio de compra; en productos por peso es por kilo."""
        return f'${self.cost_price:,.2f}'.replace(',', 'X').replace('.', ',').replace('X', '.') + (
            ' / kg' if self.por_peso else '')

    @property
    def stock_texto(self):
        """Stock actual legible (en kg para productos por peso).

        Sistema viejo (Caramelera vinculada): `current_stock` está en
        gramos. Sistema nuevo: ya está en kilos, no hace falta convertir.
        """
        if self.por_peso:
            if self.product.granel_caramelera_id:
                kilos = (self.product.current_stock / Decimal('1000')).quantize(Decimal('0.001')).normalize()
            else:
                kilos = self.product.current_stock.normalize()
            return f'{kilos:f}'.replace('.', ',') + ' kg'
        return f'{self.product.current_stock.normalize():f}'


class Purchase(models.Model):
    """Purchase order model."""
    
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('ordered', 'Pedido'),
        ('received', 'Recibido'),
        ('cancelled', 'Cancelado'),
    ]
    
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name='purchases',
        verbose_name='Proveedor'
    )
    order_number = models.CharField(
        'Número de Orden',
        max_length=50,
        unique=True
    )
    status = models.CharField(
        'Estado',
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft'
    )
    order_date = models.DateField(
        'Fecha de Pedido',
        null=True,
        blank=True
    )
    received_date = models.DateField(
        'Fecha de Recepción',
        null=True,
        blank=True
    )
    subtotal = models.DecimalField(
        'Subtotal',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    tax_percent = models.DecimalField(
        'IVA (%)',
        max_digits=5,
        decimal_places=2,
        default=Decimal('21.00'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    tax = models.DecimalField(
        'IVA ($)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total = models.DecimalField(
        'Total',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    notes = models.TextField(
        'Notas',
        blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='purchases',
        verbose_name='Creado por'
    )
    created_at = models.DateTimeField(
        'Fecha de Creación',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        'Última Actualización',
        auto_now=True
    )
    
    class Meta:
        verbose_name = 'Compra'
        verbose_name_plural = 'Compras'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.order_number} - {self.supplier.name}'


class PurchaseItem(models.Model):
    """Item in a purchase order."""
    
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Compra'
    )
    product = models.ForeignKey(
        'stocks.Product',
        on_delete=models.PROTECT,
        related_name='purchase_items',
        verbose_name='Producto'
    )
    packaging = models.ForeignKey(
        'stocks.ProductPackaging',
        on_delete=models.PROTECT,
        null=True, blank=True,
        related_name='purchase_items',
        verbose_name='Empaque',
        help_text='Si se indica, quantity es cantidad de este empaque (bulto/display/unidad). Si es null, quantity es en unidades base.',
    )
    quantity = models.DecimalField(
        'Cantidad',
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Cantidad expresada en la unidad del empaque seleccionado (o unidades base si no hay empaque). '
                  'En productos por peso son kilos.',
    )
    unit_cost = models.DecimalField(
        'Costo Unitario',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Costo por unidad del empaque seleccionado (ej: costo del bulto si packaging es bulto).',
    )
    sale_price = models.DecimalField(
        'Precio de Venta',
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Si se completa, actualiza el precio de venta del producto al recibir'
    )
    subtotal = models.DecimalField(
        'Subtotal',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    received_quantity = models.DecimalField(
        'Cantidad Recibida',
        max_digits=10,
        decimal_places=3,
        default=Decimal('0')
    )
    
    class Meta:
        verbose_name = 'Ítem de Compra'
        verbose_name_plural = 'Ítems de Compra'
    
    def __str__(self):
        return f'{self.product.name} x {self.cantidad_texto}'

    @property
    def por_peso(self):
        """True si el producto se vende por peso (la cantidad va en kilos)."""
        return bool(self.product.is_granel)

    @property
    def cantidad_texto(self):
        """Cantidad legible: '5', '2,5 kg'."""
        q = Decimal(self.quantity).normalize()
        texto = f'{q:f}'.replace('.', ',')
        return f'{texto} kg' if self.por_peso else texto

    def clean(self):
        super().clean()
        if self.quantity is not None and self.product_id and not self.por_peso:
            if Decimal(self.quantity) != Decimal(self.quantity).to_integral_value():
                raise ValidationError({
                    'quantity': f'"{self.product.name}" se compra por unidad: la cantidad tiene que ser un número entero.'
                })

    def save(self, *args, **kwargs):
        self.subtotal = self.quantity * self.unit_cost
        super().save(*args, **kwargs)
