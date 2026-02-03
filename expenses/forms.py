"""
Expenses Forms
"""
from django import forms
from .models import ExpenseCategory, Expense, RecurringExpense


class ExpenseCategoryForm(forms.ModelForm):
    """Form for expense categories."""
    
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Nombre de la categoría'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Descripción'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }


class ExpenseForm(forms.ModelForm):
    """Form for creating/editing expenses."""
    
    class Meta:
        model = Expense
        fields = [
            'category', 'description', 'amount', 'expense_date',
            'payment_method', 'receipt_number', 'supplier',
            'notes', 'receipt_image'
        ]
        widgets = {
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descripción del gasto'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01',
                'placeholder': '0.00'
            }),
            'expense_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'payment_method': forms.Select(attrs={
                'class': 'form-select'
            }),
            'receipt_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Número de factura/recibo'
            }),
            'supplier': forms.Select(attrs={
                'class': 'form-select'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Notas adicionales'
            }),
            'receipt_image': forms.FileInput(attrs={
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ExpenseCategory.objects.filter(is_active=True)
        self.fields['supplier'].required = False


class RecurringExpenseForm(forms.ModelForm):
    """Form for recurring expenses."""
    
    class Meta:
        model = RecurringExpense
        fields = [
            'category', 'description', 'amount',
            'frequency', 'next_due_date', 'is_active', 'notes'
        ]
        widgets = {
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'description': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Descripción del gasto'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-select'
            }),
            'next_due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3
            }),
        }
