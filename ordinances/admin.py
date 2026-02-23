from django.contrib import admin
from .models import Ordinance

@admin.register(Ordinance)
class OrdinanceAdmin(admin.ModelAdmin):
    list_display = ('ordinance_number', 'title', 'date_enacted', 'category', 'status')
    list_filter = ('category', 'status', 'date_enacted')
    search_fields = ('ordinance_number', 'title', 'author', 'sponsor')
