from django.contrib import admin
from .models import StockBatch, BulkToGranelTransfer, ShrinkageAudit, CarameleraComponent


@admin.register(StockBatch)
class StockBatchAdmin(admin.ModelAdmin):
    list_display = ('product', 'supplier_name', 'quantity_purchased', 'quantity_remaining',
                    'purchase_price', 'purchased_at')
    list_filter = ('product', 'purchased_at')
    search_fields = ('product__name', 'supplier_name')
    readonly_fields = ('created_at',)


@admin.register(BulkToGranelTransfer)
class BulkToGranelTransferAdmin(admin.ModelAdmin):
    list_display = ('bulk_product', 'granel_product', 'grams_transferred',
                    'granel_weighted_cost_after', 'transferred_by', 'transferred_at')
    list_filter = ('granel_product', 'transferred_at')
    readonly_fields = ('transferred_at',)


@admin.register(CarameleraComponent)
class CarameleraComponentAdmin(admin.ModelAdmin):
    list_display = ('caramelera', 'bulk_product', 'notes', 'added_at')
    list_filter = ('caramelera',)
    search_fields = ('caramelera__name', 'bulk_product__name')


@admin.register(ShrinkageAudit)
class ShrinkageAuditAdmin(admin.ModelAdmin):
    list_display = ('granel_product', 'theoretical_grams', 'actual_grams',
                    'shrinkage_grams', 'shrinkage_percent', 'reason', 'audited_at')
    list_filter = ('granel_product', 'reason', 'audited_at')
    readonly_fields = ('audited_at',)
