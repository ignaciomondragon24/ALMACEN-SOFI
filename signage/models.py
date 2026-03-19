"""
Signage Models - Visual Sign Designer System
Diseñador Visual de Carteles estilo Canva para listas de precios.
"""
import json
from django.db import models
from django.conf import settings
from decimal import Decimal


class SignTemplate(models.Model):
    """
    Plantilla visual (molde) para generación de carteles.
    Almacena la configuración visual completa como JSON.
    """

    TEMPLATE_TYPES = [
        ('simple', 'Precio Unitario'),
        ('promotional', 'Promocional (Llevá X por Y)'),
        ('bulk', 'Bulto Cerrado (Caja/Bolsa)'),
        ('weight', 'Venta al Peso (Dietética)'),
    ]

    name = models.CharField('Nombre', max_length=100)
    template_type = models.CharField(
        'Tipo de Cartel', max_length=20, choices=TEMPLATE_TYPES
    )

    # Dimensiones en mm
    width_mm = models.PositiveIntegerField('Ancho (mm)', default=50)
    height_mm = models.PositiveIntegerField('Alto (mm)', default=40)

    # Configuración visual almacenada como JSON
    layout_json = models.TextField(
        'Configuración Visual',
        default='{}',
        blank=True,
        help_text='JSON con toda la configuración visual del cartel',
    )

    is_active = models.BooleanField('Activo', default=True)
    is_default = models.BooleanField('Por Defecto', default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sign_templates',
        verbose_name='Creado por',
    )
    created_at = models.DateTimeField('Creado', auto_now_add=True)
    updated_at = models.DateTimeField('Actualizado', auto_now=True)

    class Meta:
        verbose_name = 'Plantilla de Cartel'
        verbose_name_plural = 'Plantillas de Carteles'
        ordering = ['template_type', 'name']

    def __str__(self):
        return (
            f'{self.name} ({self.get_template_type_display()}) '
            f'- {self.width_mm}x{self.height_mm}mm'
        )

    def get_layout(self):
        try:
            layout = json.loads(self.layout_json)
            if layout:
                return layout
        except (json.JSONDecodeError, TypeError):
            pass
        return self.get_default_layout(self.template_type)

    def set_layout(self, layout_dict):
        self.layout_json = json.dumps(layout_dict, ensure_ascii=False)

    @classmethod
    def get_default_layout(cls, template_type='simple'):
        defaults = {
            'simple': {
                'background_color': '#ffffff',
                'border_color': '#000000',
                'border_width': 2,
                'border_radius': 0,
                'padding': 3,
                'font_family': 'Arial, sans-serif',
                'show_store_name': False,
                'store_name': 'CHE GOLOSO',
                'store_name_bg': '#333333',
                'store_name_color': '#ffffff',
                'store_name_size': 8,
                'product_name_size': 14,
                'product_name_weight': 'bold',
                'product_name_color': '#000000',
                'gramaje_show': True,
                'gramaje_size': 9,
                'gramaje_color': '#666666',
                'price_size': 32,
                'price_weight': 'bold',
                'price_color': '#27ae60',
                'price_show_currency': True,
            },
            'promotional': {
                'background_color': '#dc3545',
                'border_color': '#a71d2a',
                'border_width': 3,
                'border_radius': 8,
                'padding': 4,
                'font_family': 'Arial, sans-serif',
                'promo_label_show': True,
                'promo_label_text': 'PROMO!!',
                'promo_label_bg': '#FFD700',
                'promo_label_color': '#cc0000',
                'promo_label_size': 12,
                'product_name_size': 12,
                'product_name_weight': 'bold',
                'product_name_color': '#ffffff',
                'unit_price_size': 14,
                'unit_price_color': '#ffffff',
                'promo_badge_size': 24,
                'promo_badge_color': '#FFD700',
                'promo_price_size': 28,
                'promo_price_weight': 'bold',
                'promo_price_color': '#ffffff',
                'price_show_currency': True,
            },
            'bulk': {
                'background_color': '#ffffff',
                'border_color': '#2c3e50',
                'border_width': 3,
                'border_radius': 4,
                'padding': 5,
                'font_family': 'Arial, sans-serif',
                'show_store_name': False,
                'product_name_size': 16,
                'product_name_weight': 'bold',
                'product_name_color': '#000000',
                'total_price_size': 28,
                'total_price_weight': 'bold',
                'total_price_color': '#e74c3c',
                'package_info_size': 12,
                'package_info_color': '#2c3e50',
                'package_info_weight': 'bold',
                'price_show_currency': True,
            },
            'weight': {
                'background_color': '#ffffff',
                'border_color': '#000000',
                'border_width': 2,
                'border_radius': 0,
                'padding': 4,
                'font_family': 'Arial, sans-serif',
                'show_store_name': False,
                'product_name_size': 14,
                'product_name_weight': 'bold',
                'product_name_color': '#000000',
                'price_100g_size': 12,
                'price_100g_color': '#000000',
                'price_250g_size': 14,
                'price_250g_color': '#000000',
                'price_1kg_size': 20,
                'price_1kg_weight': 'bold',
                'price_1kg_color': '#e74c3c',
                'price_show_currency': True,
                'show_dividers': True,
                'divider_color': '#cccccc',
            },
        }
        return defaults.get(template_type, defaults['simple'])

    @classmethod
    def get_default_dimensions(cls, template_type):
        dimensions = {
            'simple': (50, 40),
            'promotional': (70, 50),
            'bulk': (100, 70),
            'weight': (100, 70),
        }
        return dimensions.get(template_type, (50, 40))


class SignBatch(models.Model):
    """Lote de carteles generados para impresión."""

    PAPER_SIZES = [
        ('A4', 'A4 (210×297mm)'),
        ('letter', 'Carta (216×279mm)'),
        ('legal', 'Oficio (216×356mm)'),
    ]

    template = models.ForeignKey(
        SignTemplate,
        on_delete=models.CASCADE,
        related_name='batches',
        verbose_name='Plantilla',
    )
    paper_size = models.CharField(
        'Tamaño de Papel',
        max_length=10,
        choices=PAPER_SIZES,
        default='A4',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sign_batches',
        verbose_name='Creado por',
    )
    created_at = models.DateTimeField('Creado', auto_now_add=True)
    notes = models.TextField('Notas', blank=True)

    class Meta:
        verbose_name = 'Lote de Carteles'
        verbose_name_plural = 'Lotes de Carteles'
        ordering = ['-created_at']

    def __str__(self):
        return (
            f'Lote #{self.pk} - {self.template.name} '
            f'({self.created_at.strftime("%d/%m/%Y %H:%M")})'
        )

    @property
    def total_signs(self):
        return sum(item.copies for item in self.items.all())

    def get_paper_dimensions(self):
        sizes = {
            'A4': (210, 297),
            'letter': (216, 279),
            'legal': (216, 356),
        }
        return sizes.get(self.paper_size, (210, 297))


class SignItem(models.Model):
    """Datos de un cartel individual dentro de un lote."""

    PACKAGE_TYPES = [
        ('caja', 'Caja'),
        ('bolsa', 'Bolsa'),
        ('pack', 'Pack'),
        ('display', 'Display'),
    ]

    batch = models.ForeignKey(
        SignBatch,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Lote',
    )
    product = models.ForeignKey(
        'stocks.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sign_items',
        verbose_name='Producto',
    )

    # Campos comunes (prevalecen sobre datos del producto)
    custom_name = models.CharField('Nombre Custom', max_length=200, blank=True)
    custom_price = models.DecimalField(
        'Precio Custom', max_digits=10, decimal_places=2, null=True, blank=True
    )
    gramaje = models.CharField('Gramaje', max_length=50, blank=True)

    # Campos Promocional
    promo_quantity = models.PositiveIntegerField(
        'Cantidad Promo', null=True, blank=True
    )
    promo_price = models.DecimalField(
        'Precio Promo', max_digits=10, decimal_places=2, null=True, blank=True
    )

    # Campos Bulto
    package_type = models.CharField(
        'Tipo Empaque', max_length=20, choices=PACKAGE_TYPES, blank=True
    )
    quantity_per_package = models.CharField(
        'Contenido Empaque',
        max_length=50,
        blank=True,
        help_text='Ej: 30U, 1kg, 500g',
    )

    # Campos Venta al Peso
    price_100g = models.DecimalField(
        'Precio 100g', max_digits=10, decimal_places=2, null=True, blank=True
    )
    price_250g = models.DecimalField(
        'Precio ¼kg', max_digits=10, decimal_places=2, null=True, blank=True
    )
    price_1kg = models.DecimalField(
        'Precio 1kg', max_digits=10, decimal_places=2, null=True, blank=True
    )

    copies = models.PositiveIntegerField('Copias', default=1)
    order = models.PositiveIntegerField('Orden', default=0)

    class Meta:
        verbose_name = 'Cartel Individual'
        verbose_name_plural = 'Carteles Individuales'
        ordering = ['order', 'pk']

    def __str__(self):
        return f'{self.display_name} (x{self.copies})'

    @property
    def display_name(self):
        return self.custom_name or (self.product.name if self.product else 'Sin nombre')

    @property
    def display_price(self):
        if self.custom_price is not None:
            return self.custom_price
        if self.product:
            return self.product.sale_price
        return Decimal('0.00')
