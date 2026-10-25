from django.contrib import admin

from .models import Customer, FiadoEntry


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'is_active', 'created_at')
    search_fields = ('name', 'phone')
    list_filter = ('is_active',)


@admin.register(FiadoEntry)
class FiadoEntryAdmin(admin.ModelAdmin):
    list_display = ('customer', 'entry_type', 'amount', 'ticket_number', 'created_at', 'voided_at')
    list_filter = ('entry_type',)
    search_fields = ('customer__name', 'ticket_number')
    raw_id_fields = ('pos_transaction', 'cash_movement', 'cash_shift')
