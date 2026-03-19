from django.contrib import admin
from .models import SignTemplate, SignBatch, SignItem


class SignItemInline(admin.TabularInline):
    model = SignItem
    extra = 0
    fields = ('product', 'custom_name', 'custom_price', 'copies', 'order')
    raw_id_fields = ('product',)


@admin.register(SignTemplate)
class SignTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'template_type', 'width_mm', 'height_mm',
        'is_default', 'is_active', 'created_by', 'updated_at',
    )
    list_filter = ('template_type', 'is_active', 'is_default')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SignBatch)
class SignBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'template', 'paper_size', 'total_signs', 'created_by', 'created_at')
    list_filter = ('template', 'paper_size', 'created_at')
    date_hierarchy = 'created_at'
    inlines = [SignItemInline]
