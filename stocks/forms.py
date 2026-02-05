"""
Stocks Forms
"""
from django import forms
from .models import Product, ProductCategory, UnitOfMeasure


class ProductForm(forms.ModelForm):
    """Form for creating/editing products."""
    
    class Meta:
        model = Product
        fields = [
            'sku', 'barcode', 'name', 'description', 'category', 'unit_of_measure',
            'purchase_price', 'sale_price', 'current_stock', 'min_stock', 'max_stock',
            'location', 'image', 'is_active', 'is_quick_access', 'quick_access_color',
            'quick_access_icon', 'quick_access_position'
        ]
        widgets = {
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'unit_of_measure': forms.Select(attrs={'class': 'form-select'}),
            'purchase_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sale_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'current_stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'min_stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'max_stock': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_quick_access': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'quick_access_color': forms.TextInput(attrs={'class': 'form-control', 'type': 'color'}),
            'quick_access_icon': forms.TextInput(attrs={'class': 'form-control'}),
            'quick_access_position': forms.NumberInput(attrs={'class': 'form-control'}),
        }


class CategoryForm(forms.ModelForm):
    """Form for categories."""
    
    class Meta:
        model = ProductCategory
        fields = ['name', 'description', 'parent', 'default_margin_percent', 'color', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'parent': forms.Select(attrs={'class': 'form-select'}),
            'default_margin_percent': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
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
    
    new_quantity = forms.IntegerField(
        label='Nueva Cantidad',
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '1', 'min': '0'})
    )
    reason = forms.CharField(
        label='Motivo del Ajuste',
        max_length=500,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
