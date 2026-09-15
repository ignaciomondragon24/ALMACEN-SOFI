"""
Purchase Admin Configuration
"""
from django.contrib import admin
from .models import Supplier, SupplierProduct, Purchase, PurchaseItem


class PurchaseItemInline(admin.TabularInline):
    model = PurchaseItem
    extra = 1
    readonly_fields = ['subtotal']


class SupplierProductInline(admin.TabularInline):
    model = SupplierProduct
    extra = 1
    autocomplete_fields = ['product']


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ['name', 'contact_name', 'phone', 'email', 'cuit', 'order_day', 'is_active']
    list_filter = ['is_active', 'order_day', 'created_at']
    search_fields = ['name', 'contact_name', 'cuit', 'email']
    ordering = ['name']
    inlines = [SupplierProductInline]


@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = ['product', 'supplier', 'cost_price', 'is_active']
    list_filter = ['is_active', 'supplier']
    search_fields = ['product__name', 'supplier__name']
    autocomplete_fields = ['product']


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = [
        'order_number', 'supplier', 'status', 'order_date',
        'total', 'created_by', 'created_at'
    ]
    list_filter = ['status', 'order_date', 'supplier']
    search_fields = ['order_number', 'supplier__name']
    readonly_fields = ['order_number', 'subtotal', 'total', 'created_at', 'updated_at']
    inlines = [PurchaseItemInline]
    date_hierarchy = 'created_at'


@admin.register(PurchaseItem)
class PurchaseItemAdmin(admin.ModelAdmin):
    list_display = ['purchase', 'product', 'quantity', 'unit_cost', 'subtotal']
    list_filter = ['purchase__status']
    search_fields = ['purchase__order_number', 'product__name']
