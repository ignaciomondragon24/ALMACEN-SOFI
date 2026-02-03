from django.contrib import admin
from .models import Promotion, PromotionProduct


class PromotionProductInline(admin.TabularInline):
    model = PromotionProduct
    extra = 1
    autocomplete_fields = ['product']


@admin.register(Promotion)
class PromotionAdmin(admin.ModelAdmin):
    list_display = ('name', 'promo_type', 'status', 'priority', 'start_date', 'end_date', 
                   'is_combinable', 'usages', 'is_valid_today')
    list_filter = ('status', 'promo_type', 'is_combinable', 'start_date')
    search_fields = ('name', 'description')
    inlines = [PromotionProductInline]
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'description', 'promo_type', 'status')
        }),
        ('Vigencia', {
            'fields': ('start_date', 'end_date', 'priority', 'is_combinable')
        }),
        ('Días Activos', {
            'fields': (('monday', 'tuesday', 'wednesday', 'thursday'), 
                      ('friday', 'saturday', 'sunday'))
        }),
        ('Horario', {
            'fields': ('hour_start', 'hour_end'),
            'classes': ('collapse',)
        }),
        ('Condiciones', {
            'fields': ('min_quantity', 'min_purchase_amount', 'max_uses_per_sale')
        }),
        ('Configuración NxM', {
            'fields': ('quantity_required', 'quantity_charged'),
            'classes': ('collapse',)
        }),
        ('Descuentos', {
            'fields': ('discount_percent', 'discount_amount', 'final_price', 'second_unit_discount')
        }),
        ('Estadísticas', {
            'fields': ('usages', 'created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('usages', 'created_at', 'updated_at')
