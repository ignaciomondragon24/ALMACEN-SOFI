"""
Stocks Models - Products, Categories, Units of Measure, Stock Movements
"""
from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
import random
import string


class ProductCategory(models.Model):
    """Product category model."""
    
    name = models.CharField(
        'Nombre',
        max_length=100,
        unique=True
    )
    description = models.TextField(
        'Descripción',
        blank=True
    )
    parent = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subcategories',
        verbose_name='Categoría Padre'
    )
    default_margin_percent = models.DecimalField(
        'Margen por defecto (%)',
        max_digits=5,
        decimal_places=2,
        default=30.00,
        validators=[MinValueValidator(Decimal('0'))]
    )
    color = models.CharField(
        'Color',
        max_length=7,
        default='#3498db',
        help_text='Código hexadecimal del color'
    )
    is_active = models.BooleanField(
        'Activo',
        default=True
    )
    created_at = models.DateTimeField(
        'Fecha de creación',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        'Última actualización',
        auto_now=True
    )
    
    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering = ['name']
    
    def __str__(self):
        if self.parent:
            return f'{self.parent.name} > {self.name}'
        return self.name
    
    @property
    def full_path(self):
        """Return full category path."""
        if self.parent:
            return f'{self.parent.full_path} > {self.name}'
        return self.name
    
    @property
    def product_count(self):
        """Return number of products in this category."""
        return self.products.filter(is_active=True).count()


class UnitOfMeasure(models.Model):
    """Unit of measure model."""
    
    UNIT_TYPES = [
        ('unit', 'Unidad'),
        ('weight', 'Peso'),
        ('volume', 'Volumen'),
        ('length', 'Longitud'),
    ]
    
    name = models.CharField(
        'Nombre',
        max_length=50,
        unique=True
    )
    abbreviation = models.CharField(
        'Abreviatura',
        max_length=10
    )
    symbol = models.CharField(
        'Símbolo',
        max_length=5,
        blank=True
    )
    unit_type = models.CharField(
        'Tipo',
        max_length=20,
        choices=UNIT_TYPES,
        default='unit'
    )
    is_active = models.BooleanField(
        'Activo',
        default=True
    )
    
    class Meta:
        verbose_name = 'Unidad de Medida'
        verbose_name_plural = 'Unidades de Medida'
        ordering = ['name']
    
    def __str__(self):
        return f'{self.name} ({self.abbreviation})'


class Product(models.Model):
    """Product model."""
    
    sku = models.CharField(
        'SKU',
        max_length=50,
        unique=True
    )
    barcode = models.CharField(
        'Código de Barras',
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )
    name = models.CharField(
        'Nombre',
        max_length=200
    )
    description = models.TextField(
        'Descripción',
        blank=True
    )
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name='Categoría'
    )
    unit_of_measure = models.ForeignKey(
        UnitOfMeasure,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='products',
        verbose_name='Unidad de Medida'
    )
    
    # Prices
    purchase_price = models.DecimalField(
        'Precio de Compra',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    sale_price = models.DecimalField(
        'Precio de Venta',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    cost_price = models.DecimalField(
        'Costo Promedio',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    # Stock
    current_stock = models.DecimalField(
        'Stock Actual',
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    min_stock = models.DecimalField(
        'Stock Mínimo',
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Alerta cuando el stock llegue a este nivel'
    )
    max_stock = models.DecimalField(
        'Stock Máximo',
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))]
    )
    
    # Additional info
    location = models.CharField(
        'Ubicación',
        max_length=50,
        blank=True,
        help_text='Ubicación física en el almacén'
    )
    image = models.ImageField(
        'Imagen',
        upload_to='products/',
        blank=True,
        null=True
    )
    is_active = models.BooleanField(
        'Activo',
        default=True
    )
    is_quick_access = models.BooleanField(
        'Acceso Rápido POS',
        default=False,
        help_text='Mostrar como botón de acceso rápido en el POS'
    )
    quick_access_color = models.CharField(
        'Color Acceso Rápido',
        max_length=7,
        default='#3498db',
        help_text='Código hexadecimal del color para botón POS'
    )
    quick_access_icon = models.CharField(
        'Icono Acceso Rápido',
        max_length=50,
        default='fa-box',
        help_text='Clase de icono Font Awesome'
    )
    quick_access_position = models.PositiveIntegerField(
        'Posición Acceso Rápido',
        default=0
    )
    
    # Bulk / Weight selling options
    is_bulk = models.BooleanField(
        'Producto a Granel',
        default=False,
        help_text='Productos que se venden por peso (gomitas, fiambres, etc)'
    )
    allow_sell_by_amount = models.BooleanField(
        'Permite Venta por Monto',
        default=False,
        help_text='Permite ingresar "$500 de gomitas" y calcular la cantidad'
    )
    bulk_unit = models.CharField(
        'Unidad de Granel',
        max_length=10,
        choices=[
            ('kg', 'Kilogramo'),
            ('g', 'Gramo'),
            ('lt', 'Litro'),
            ('ml', 'Mililitro'),
        ],
        default='kg',
        blank=True
    )
    
    # Parent-child relationship for presentations
    parent_product = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='child_products',
        verbose_name='Producto Padre',
        help_text='Para cajas/bultos, indica el producto individual que contiene'
    )
    units_per_package = models.DecimalField(
        'Unidades por Paquete',
        max_digits=10,
        decimal_places=3,
        default=Decimal('1.000'),
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text='Cuántas unidades del producto hijo contiene (ej: 24 para caja de 24)'
    )
    
    # Timestamps
    created_at = models.DateTimeField(
        'Fecha de creación',
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        'Última actualización',
        auto_now=True
    )
    
    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['name']
        indexes = [
            models.Index(fields=['sku']),
            models.Index(fields=['barcode']),
            models.Index(fields=['name']),
            models.Index(fields=['is_active']),
            models.Index(fields=['current_stock']),
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Auto-generate SKU if not provided
        if not self.sku:
            self.sku = self.generate_sku()
        super().save(*args, **kwargs)
    
    def generate_sku(self):
        """Generate a unique SKU."""
        prefix = 'PRD'
        suffix = ''.join(random.choices(string.digits, k=6))
        return f'{prefix}{suffix}'
    
    @property
    def margin_percent(self):
        """Calculate profit margin percentage."""
        if self.purchase_price and self.purchase_price > 0:
            margin = ((self.sale_price - self.purchase_price) / self.purchase_price) * 100
            return round(margin, 2)
        return 0
    
    @property
    def profit(self):
        """Calculate profit per unit."""
        return self.sale_price - self.purchase_price
    
    @property
    def is_low_stock(self):
        """Check if stock is below minimum."""
        return self.current_stock <= self.min_stock
    
    @property
    def stock_value(self):
        """Calculate total stock value at cost."""
        return self.current_stock * self.cost_price
    
    @property
    def stock_value_sale(self):
        """Calculate total stock value at sale price."""
        return self.current_stock * self.sale_price
    
    @property
    def has_children(self):
        """Check if this product has child products (is a container/package)."""
        return self.child_products.exists()
    
    @property
    def is_child(self):
        """Check if this product is a child of another product."""
        return self.parent_product is not None
    
    def calculate_quantity_for_amount(self, amount):
        """
        Calculate quantity that can be purchased for a given amount.
        Used for bulk products sold by weight.
        Returns: (quantity, actual_total)
        """
        if self.sale_price <= 0:
            return Decimal('0'), Decimal('0')
        
        quantity = Decimal(str(amount)) / self.sale_price
        
        # Round to 3 decimals for weight products
        if self.is_bulk:
            quantity = quantity.quantize(Decimal('0.001'))
        else:
            quantity = quantity.quantize(Decimal('1'))
        
        actual_total = quantity * self.sale_price
        return quantity, actual_total
    
    def get_unit_display(self):
        """Get display string for the unit."""
        if self.is_bulk and self.bulk_unit:
            units = {
                'kg': 'kg',
                'g': 'gr',
                'lt': 'lt',
                'ml': 'ml',
            }
            return units.get(self.bulk_unit, 'unid')
        elif self.unit_of_measure:
            return self.unit_of_measure.abbreviation
        return 'unid'
    
    def convert_to_child_units(self, parent_quantity):
        """
        Convert parent quantity to child units.
        e.g.: 2 boxes of 24 = 48 units
        """
        if self.has_children:
            first_child = self.child_products.first()
            if first_child:
                return parent_quantity * self.units_per_package
        return parent_quantity
    
    def convert_to_parent_units(self, child_quantity):
        """
        Convert child quantity to parent units.
        e.g.: 48 units = 2 boxes of 24
        """
        if self.parent_product and self.parent_product.units_per_package > 0:
            return child_quantity / self.parent_product.units_per_package
        return child_quantity


class StockMovement(models.Model):
    """Stock movement model."""
    
    MOVEMENT_TYPES = [
        ('purchase', 'Compra'),
        ('sale', 'Venta'),
        ('adjustment_in', 'Ajuste Entrada'),
        ('adjustment_out', 'Ajuste Salida'),
        ('transfer_in', 'Transferencia Entrada'),
        ('transfer_out', 'Transferencia Salida'),
        ('return_in', 'Devolución Entrada'),
        ('return_out', 'Devolución Salida'),
    ]
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='stock_movements',
        verbose_name='Producto'
    )
    movement_type = models.CharField(
        'Tipo de Movimiento',
        max_length=20,
        choices=MOVEMENT_TYPES
    )
    quantity = models.DecimalField(
        'Cantidad',
        max_digits=10,
        decimal_places=3
    )
    unit_cost = models.DecimalField(
        'Costo Unitario',
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    stock_before = models.DecimalField(
        'Stock Antes',
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000')
    )
    stock_after = models.DecimalField(
        'Stock Después',
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000')
    )
    reference = models.CharField(
        'Referencia',
        max_length=100,
        blank=True,
        help_text='Ej: Compra #123, Venta #456'
    )
    reference_id = models.PositiveIntegerField(
        'ID Referencia',
        null=True,
        blank=True
    )
    notes = models.TextField(
        'Notas',
        blank=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        verbose_name='Creado por'
    )
    created_at = models.DateTimeField(
        'Fecha',
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = 'Movimiento de Stock'
        verbose_name_plural = 'Movimientos de Stock'
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.get_movement_type_display()} - {self.product.name} ({self.quantity})'


class ProductPresentation(models.Model):
    """Product presentation (different packaging)."""
    
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='presentations',
        verbose_name='Producto'
    )
    name = models.CharField(
        'Nombre',
        max_length=100,
        help_text='Ej: Pack x 6, Caja x 12'
    )
    quantity = models.DecimalField(
        'Cantidad de Unidades',
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    barcode = models.CharField(
        'Código de Barras',
        max_length=50,
        unique=True,
        blank=True,
        null=True
    )
    sale_price = models.DecimalField(
        'Precio de Venta',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    is_active = models.BooleanField(
        'Activo',
        default=True
    )
    
    class Meta:
        verbose_name = 'Presentación'
        verbose_name_plural = 'Presentaciones'
        ordering = ['product', 'quantity']
    
    def __str__(self):
        return f'{self.product.name} - {self.name}'
    
    @property
    def unit_price(self):
        """Calculate unit price for this presentation."""
        if self.quantity > 0:
            return self.sale_price / self.quantity
        return Decimal('0.00')
