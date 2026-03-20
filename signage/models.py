import json

from django.db import models
from django.conf import settings


class SignTemplate(models.Model):
    """Plantilla (molde) de cartel para inyectar datos de productos."""

    SIGN_TYPES = [
        ('simple', 'Cartel Simple (Precio Unitario)'),
        ('promo', 'Cartel Promocional (Llevá X por Y)'),
        ('bulk', 'Cartel de Bulto Cerrado (Caja/Bolsa)'),
        ('weight', 'Cartel de Venta al Peso'),
    ]

    PRESET_SIZES = {
        'simple': [
            {'label': '5 × 4 cm', 'width': 50, 'height': 40},
            {'label': '5 × 3 cm', 'width': 50, 'height': 30},
        ],
        'promo': [
            {'label': '7 × 5 cm', 'width': 70, 'height': 50},
            {'label': '10 × 7 cm', 'width': 100, 'height': 70},
        ],
        'bulk': [
            {'label': '10 × 7 cm', 'width': 100, 'height': 70},
            {'label': '14 × 10 cm (A6)', 'width': 140, 'height': 100},
        ],
        'weight': [
            {'label': '10 × 7 cm (apaisado)', 'width': 100, 'height': 70},
            {'label': '14 × 10 cm', 'width': 140, 'height': 100},
        ],
    }

    name = models.CharField('Nombre', max_length=200)
    sign_type = models.CharField('Tipo de Cartel', max_length=20, choices=SIGN_TYPES)
    width_mm = models.PositiveIntegerField('Ancho (mm)')
    height_mm = models.PositiveIntegerField('Alto (mm)')
    layout_json = models.TextField('Diseño (JSON)', default='{}', blank=True)

    @property
    def layout(self):
        try:
            return json.loads(self.layout_json) if self.layout_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @layout.setter
    def layout(self, value):
        self.layout_json = json.dumps(value) if value else '{}'

    is_active = models.BooleanField('Activo', default=True)
    is_default = models.BooleanField('Predeterminado', default=False)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Creado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Plantilla de Cartel'
        verbose_name_plural = 'Plantillas de Carteles'
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.name} ({self.get_sign_type_display()}) - {self.width_mm}×{self.height_mm}mm"

    @property
    def size_label(self):
        w_cm = self.width_mm / 10
        h_cm = self.height_mm / 10
        return f"{w_cm:.0f} × {h_cm:.0f} cm"

    @classmethod
    def get_type_variables(cls, sign_type):
        """Variables disponibles para cada tipo de cartel."""
        VARIABLES = {
            'simple': [
                {'key': 'nombre_producto', 'label': 'Nombre del Producto', 'sample': 'SALADIX'},
                {'key': 'gramaje', 'label': 'Gramaje', 'sample': '100g'},
                {'key': 'precio_unitario', 'label': 'Precio Unitario', 'sample': '$790'},
            ],
            'promo': [
                {'key': 'nombre_producto', 'label': 'Nombre del Producto', 'sample': 'TURRON MISKY'},
                {'key': 'precio_unitario', 'label': 'Precio Unitario', 'sample': '$180'},
                {'key': 'cantidad_promo', 'label': 'Cantidad Promo', 'sample': '3'},
                {'key': 'precio_promo', 'label': 'Precio Promo', 'sample': '$500'},
                {'key': 'etiqueta_promo', 'label': 'Etiqueta (PROMO!!)', 'sample': 'PROMO!!'},
            ],
            'bulk': [
                {'key': 'nombre_producto', 'label': 'Nombre del Producto', 'sample': 'FEELING'},
                {'key': 'precio_total', 'label': 'Precio Total', 'sample': '$11.500'},
                {'key': 'tipo_empaque', 'label': 'Tipo de Empaque', 'sample': 'CAJA'},
                {'key': 'contenido_empaque', 'label': 'Contenido', 'sample': 'X 30U.'},
            ],
            'weight': [
                {'key': 'nombre_producto', 'label': 'Nombre del Producto', 'sample': 'ALMENDRAS PELADAS'},
                {'key': 'precio_100g', 'label': 'Precio 100g', 'sample': '$3.200'},
                {'key': 'precio_250g', 'label': 'Precio ¼ Kg', 'sample': '$7.350'},
                {'key': 'precio_1kg', 'label': 'Precio 1 Kg', 'sample': '$29.400'},
            ],
        }
        return VARIABLES.get(sign_type, [])


class SignBatch(models.Model):
    """Lote de carteles generados."""

    PAPER_SIZES = [
        ('A4', 'A4 (210 × 297 mm)'),
        ('A3', 'A3 (297 × 420 mm)'),
        ('letter', 'Carta (216 × 279 mm)'),
    ]

    name = models.CharField('Nombre', max_length=200, blank=True)
    template = models.ForeignKey(
        SignTemplate, on_delete=models.CASCADE,
        related_name='batches', verbose_name='Plantilla'
    )
    paper_size = models.CharField(
        'Tamaño de Papel', max_length=10,
        choices=PAPER_SIZES, default='A4'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Creado por'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Lote de Carteles'
        verbose_name_plural = 'Lotes de Carteles'
        ordering = ['-created_at']

    def __str__(self):
        return f"Lote #{self.pk} - {self.template.name} ({self.created_at:%d/%m/%Y})"

    @property
    def total_signs(self):
        return sum(item.copies for item in self.items.all())


class SignItem(models.Model):
    """Item individual en un lote de carteles."""

    batch = models.ForeignKey(
        SignBatch, on_delete=models.CASCADE,
        related_name='items', verbose_name='Lote'
    )
    product = models.ForeignKey(
        'stocks.Product', on_delete=models.SET_NULL,
        null=True, blank=True, verbose_name='Producto'
    )
    data_json = models.TextField('Datos (JSON)', default='{}', blank=True)

    @property
    def data(self):
        try:
            return json.loads(self.data_json) if self.data_json else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    @data.setter
    def data(self, value):
        self.data_json = json.dumps(value) if value else '{}'
    copies = models.PositiveIntegerField('Copias', default=1)
    order = models.PositiveIntegerField('Orden', default=0)

    class Meta:
        verbose_name = 'Item de Cartel'
        verbose_name_plural = 'Items de Carteles'
        ordering = ['order']

    def __str__(self):
        name = self.data.get('nombre_producto', f'Item #{self.pk}')
        return f"{name} ×{self.copies}"
