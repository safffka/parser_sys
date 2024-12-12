from django.contrib import admin
from .models import PDFFile, ParserConfiguration

@admin.register(PDFFile)
class PDFFileAdmin(admin.ModelAdmin):
    list_display = ('name', 'file_path', 'downloaded_at')
    search_fields = ('name',)

@admin.register(ParserConfiguration)
class ParserConfigurationAdmin(admin.ModelAdmin):
    list_display = ('interval_minutes', 'last_run', 'last_error')
    # Admin can edit interval_minutes directly here
