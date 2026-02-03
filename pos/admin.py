from django.contrib import admin
from .models import POSSession, POSTransaction, POSTransactionItem, POSPayment, QuickAccessButton


@admin.register(POSSession)
class POSSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'cash_shift', 'opened_at', 'closed_at', 'status', 'total_transactions', 'total_amount')
    list_filter = ('status', 'opened_at')
    search_fields = ('cash_shift__cash_register__code', 'cash_shift__cashier__username')
    date_hierarchy = 'opened_at'


@admin.register(POSTransaction)
class POSTransactionAdmin(admin.ModelAdmin):
    list_display = ('ticket_number', 'session', 'status', 'subtotal', 'discount_total', 'total', 
                   'items_count', 'created_at', 'completed_at')
    list_filter = ('status', 'created_at')
    search_fields = ('ticket_number',)
    date_hierarchy = 'created_at'
    readonly_fields = ('ticket_number', 'created_at', 'updated_at', 'completed_at', 'cancelled_at', 'suspended_at')


@admin.register(POSTransactionItem)
class POSTransactionItemAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'product', 'quantity', 'unit_price', 'discount', 'subtotal', 'promotion_name')
    list_filter = ('transaction__status',)
    search_fields = ('transaction__ticket_number', 'product__name')


@admin.register(POSPayment)
class POSPaymentAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'payment_method', 'amount', 'reference', 'created_at')
    list_filter = ('payment_method', 'created_at')
    search_fields = ('transaction__ticket_number', 'reference')
    date_hierarchy = 'created_at'


@admin.register(QuickAccessButton)
class QuickAccessButtonAdmin(admin.ModelAdmin):
    list_display = ('product', 'name', 'color', 'icon', 'position', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('product__name', 'name')
    ordering = ('position',)
