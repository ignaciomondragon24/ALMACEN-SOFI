from django.contrib import admin
from .models import SignTemplate, SignGeneration


@admin.register(SignTemplate)
class SignTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'size', 'orientation', 'is_default', 'is_active')
    list_filter = ('template_type', 'size', 'is_active')
    search_fields = ('name',)


@admin.register(SignGeneration)
class SignGenerationAdmin(admin.ModelAdmin):
    list_display = ('id', 'template', 'generated_by', 'generated_at')
    list_filter = ('template', 'generated_at')
    date_hierarchy = 'generated_at'
