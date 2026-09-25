"""
Stocks Forms
"""
from django import forms
from django.db.models import Q
from decimal import Decimal
from .models import Product, ProductCategory, UnitOfMeasure, ProductPackaging


class ProductForm(forms.ModelForm):
    """Form for creating/editing products."""
    
    class Meta:
        model = Product
        fields = [
            'sku', 'barcode', 'name', 'description', 'category', 'unit_of_measure',
            'cost_price', 'sale_price', 'current_stock', 'min_stock', 'max_stock',
            'location', 'image', 'is_active', 'is_quick_access', 'quick_access_color',
            'quick_access_icon', 'quick_access_position',
            'weight_per_unit_grams', 'marca',
            # Venta por peso: todo se carga acá mismo, en el producto — no hay
            # pantalla ni app aparte. `is_granel` es el checkbox "se vende por
            # peso"; los 4 campos de tramos son opcionales (0 = sin cargar).
            'is_granel', 'sale_price_250g', 'sale_price_500g',
            'oferta_price_250g', 'oferta_price_500g',
        ]
        widgets = {
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'unit_of_measure': forms.Select(attrs={'class': 'form-select'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'current_stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'min_stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'max_stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_quick_access': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'quick_access_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'quick_access_icon': forms.TextInput(attrs={'class': 'form-control'}),
            'quick_access_position': forms.NumberInput(attrs={'class': 'form-control'}),
            'weight_per_unit_grams': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'marca': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Arcor, Stani...'}),
            'is_granel': forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_is_granel'}),
            'sale_price_250g': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'sale_price_500g': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'oferta_price_250g': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
            'oferta_price_500g': forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Tanto barcode como sku son opcionales a nivel form: el usuario
        # puede ingresar uno u otro. La validación cruzada está en clean().
        self.fields['barcode'].required = False
        self.fields['sku'].required = False
        self.fields['quick_access_color'].required = False
        self.fields['quick_access_icon'].required = False
        self.fields['quick_access_position'].required = False
        self.fields['weight_per_unit_grams'].required = False
        self.fields['is_granel'].required = False
        self.fields['sale_price_250g'].required = False
        self.fields['sale_price_500g'].required = False
        self.fields['oferta_price_250g'].required = False
        self.fields['oferta_price_500g'].required = False

    def clean_barcode(self):
        val = (self.cleaned_data.get('barcode') or '').strip()
        return val or None

    def clean_sku(self):
        # SKU también se normaliza (espacios) — vacío se deja para que
        # save() autogenere uno si tampoco se proveyó barcode.
        return (self.cleaned_data.get('sku') or '').strip()

    def clean_weight_per_unit_grams(self):
        val = self.cleaned_data.get('weight_per_unit_grams')
        if val is None:
            return Decimal('0.00')
        return val

    def _clean_tramo_precio(self, campo):
        val = self.cleaned_data.get(campo)
        if val is None:
            return Decimal('0')
        return val

    def clean_sale_price_250g(self):
        return self._clean_tramo_precio('sale_price_250g')

    def clean_sale_price_500g(self):
        return self._clean_tramo_precio('sale_price_500g')

    def clean_oferta_price_250g(self):
        return self._clean_tramo_precio('oferta_price_250g')

    def clean_oferta_price_500g(self):
        return self._clean_tramo_precio('oferta_price_500g')

    def clean_current_stock(self):
        """El stock se cuenta en unidades enteras (piezas), nunca fracciones.

        Excepción: productos que se venden por peso (`is_granel`) cuentan su
        stock en kilos, con decimales — necesitan precisión de balanza.

        Solo se valida al crear: al editar, el campo viene deshabilitado (el stock
        se corrige por "Conteo Físico") y no hay que romper la edición de un
        producto viejo que ya tuviera algún resto decimal de antes de este cambio.
        """
        val = self.cleaned_data.get('current_stock')
        ya_existe = bool(self.instance and self.instance.pk)
        es_por_peso = self.data.get('is_granel') in ('on', 'true', 'True', '1')
        if val is not None and not ya_existe and not es_por_peso and val != val.to_integral_value():
            raise forms.ValidationError('El stock se cuenta en unidades enteras, sin decimales.')
        return val

    def clean(self):
        """Reglas a nivel form:
        - Al menos uno de barcode o sku debe estar presente (manual).
        - El barcode no debe colisionar con OTRO producto activo. Productos
          inactivos con sufijo `_deleted_` no compiten porque su valor real
          fue liberado.
        """
        cleaned = super().clean()
        barcode = cleaned.get('barcode')
        sku = (cleaned.get('sku') or '').strip()

        if not barcode and not sku:
            raise forms.ValidationError(
                'Debe ingresar un código de barras o un SKU manual.'
            )

        if barcode:
            qs = Product.objects.filter(barcode=barcode, is_active=True)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                self.add_error(
                    'barcode',
                    'Ya existe un producto activo con este código de barras.'
                )
        return cleaned


class CategoryForm(forms.ModelForm):
    """Form for categories."""
    
    class Meta:
        model = ProductCategory
        fields = ['name', 'description', 'parent', 'default_margin_percent', 'color', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'default_margin_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '1'}),
            'color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class UnitForm(forms.ModelForm):
    """Form for units of measure."""
    
    class Meta:
        model = UnitOfMeasure
        fields = ['name', 'abbreviation', 'symbol', 'unit_type', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'abbreviation': forms.TextInput(attrs={'class': 'form-control'}),
            'symbol': forms.TextInput(attrs={'class': 'form-control'}),
            'unit_type': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class StockAdjustmentForm(forms.Form):
    """Form for stock adjustments."""

    new_quantity = forms.DecimalField(
        label='Nueva Cantidad',
        min_value=Decimal('0'),
        decimal_places=3,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'})
    )
    reason = forms.CharField(
        label='Motivo del Ajuste',
        max_length=500,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    purchase_price = forms.DecimalField(
        label='Costo Unitario de Compra',
        min_value=Decimal('0'),
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
            'placeholder': 'Precio por unidad'
        })
    )
    supplier_name = forms.CharField(
        label='Proveedor',
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nombre del proveedor'
        })
    )


class ProductPackagingForm(forms.ModelForm):
    """Formulario para configurar empaques de productos.

    Permite cambiar `packaging_type` libremente (Unidad/Display/Bulto). El
    barcode es siempre opcional: si queda vacío, la view auto-genera un
    código interno `INT-{SKU}-{TIPO}`. La unicidad activa se valida acá.
    """

    class Meta:
        model = ProductPackaging
        fields = [
            'packaging_type', 'barcode', 'name',
            'units_per_display', 'displays_per_bulk',
            'purchase_price', 'margin_percent',
            'current_stock', 'min_stock',
            'is_default', 'is_active'
        ]
        widgets = {
            'packaging_type': forms.Select(attrs={'class': 'form-select'}),
            'barcode': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Opcional — se genera INT-{SKU}-{TIPO} si se deja vacío'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ej: Bulto x 144'
            }),
            'units_per_display': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'displays_per_bulk': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'purchase_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1'
            }),
            'margin_percent': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '1'
            }),
            'current_stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.001',
                'min': '0'
            }),
            'min_stock': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0'
            }),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['barcode'].required = False

    def clean_barcode(self):
        val = (self.cleaned_data.get('barcode') or '').strip()
        return val or None

    def clean(self):
        """Valida unicidad de barcode contra empaques activos.

        Empaques inactivos con sufijo `_deleted_` no chocan porque su
        valor real fue liberado al hacer soft-delete.
        """
        cleaned = super().clean()
        barcode = cleaned.get('barcode')
        if not barcode:
            return cleaned

        qs = ProductPackaging.objects.filter(barcode=barcode, is_active=True)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            self.add_error(
                'barcode',
                'Ya existe un empaque activo con este código de barras.'
            )
        return cleaned
