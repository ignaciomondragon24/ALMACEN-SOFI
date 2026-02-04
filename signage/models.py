"""
Signage Models - Signs and price tags generation
"""
from django.db import models
from django.conf import settings


class SignTemplate(models.Model):
    """Template for sign generation."""
    
    TEMPLATE_TYPES = [
        ('price', 'Precio Simple'),
        ('offer', 'Oferta'),
        ('promotion', 'Promoción'),
        ('combo', 'Combo'),
        ('custom', 'Personalizado'),
    ]
    
    SIZE_CHOICES = [
        ('A4', 'A4 (210x297mm)'),
        ('A5', 'A5 (148x210mm)'),
        ('10x15', '10x15 cm'),
        ('custom', 'Personalizado'),
    ]
    
    ORIENTATION_CHOICES = [
        ('portrait', 'Vertical'),
        ('landscape', 'Horizontal'),
    ]
    
    name = models.CharField(
        'Nombre',
        max_length=100
    )
    template_type = models.CharField(
        'Tipo',
        max_length=20,
        choices=TEMPLATE_TYPES
    )
    size = models.CharField(
        'Tamaño',
        max_length=20,
        choices=SIZE_CHOICES,
        default='A4'
    )
    orientation = models.CharField(
        'Orientación',
        max_length=20,
        choices=ORIENTATION_CHOICES,
        default='portrait'
    )
    layout_json = models.TextField(
        'Configuración de Diseño',
        default='{}',
        blank=True,
        help_text='JSON con la configuración del diseño'
    )
    is_default = models.BooleanField(
        'Por Defecto',
        default=False
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
        verbose_name = 'Plantilla de Cartel'
        verbose_name_plural = 'Plantillas de Carteles'
        ordering = ['name']
    
    def __str__(self):
        return f'{self.name} ({self.get_template_type_display()})'


class SignGeneration(models.Model):
    """Generated sign record."""
    
    SIGN_TYPES = [
        ('price', 'Precio Simple'),
        ('promotion', 'Promoción'),
        ('offer', 'Oferta'),
        ('custom', 'Personalizado'),
    ]
    
    SIZE_CHOICES = [
        ('A4', 'A4 - Grande'),
        ('A5', 'A5 - Mediano'),
        ('10x15', '10x15 - Pequeño'),
    ]
    
    template = models.ForeignKey(
        SignTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generations',
        verbose_name='Plantilla'
    )
    products = models.ManyToManyField(
        'stocks.Product',
        related_name='sign_generations',
        verbose_name='Productos',
        blank=True
    )
    promotion = models.ForeignKey(
        'promotions.Promotion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sign_generations',
        verbose_name='Promoción'
    )
    sign_type = models.CharField(
        'Tipo de Cartel',
        max_length=20,
        choices=SIGN_TYPES,
        default='price'
    )
    sign_size = models.CharField(
        'Tamaño',
        max_length=20,
        choices=SIZE_CHOICES,
        default='A4'
    )
    custom_text = models.CharField(
        'Texto Personalizado',
        max_length=200,
        blank=True
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='sign_generations',
        verbose_name='Generado por'
    )
    file_path = models.FileField(
        'Archivo PDF',
        upload_to='signs/',
        blank=True,
        null=True
    )
    preview_image = models.ImageField(
        'Vista Previa',
        upload_to='signs/previews/',
        blank=True,
        null=True
    )
    config_json = models.TextField(
        'Configuración',
        default='{}',
        blank=True,
        help_text='JSON con la configuración del cartel'
    )
    generated_at = models.DateTimeField(
        'Fecha de Generación',
        auto_now_add=True
    )
    
    class Meta:
        verbose_name = 'Cartel Generado'
        verbose_name_plural = 'Carteles Generados'
        ordering = ['-generated_at']
    
    def __str__(self):
        return f'Cartel {self.pk} - {self.generated_at.strftime("%d/%m/%Y %H:%M")}'
