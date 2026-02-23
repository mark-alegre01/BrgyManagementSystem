from django.contrib import admin
from .models import Official

@admin.register(Official)
class OfficialAdmin(admin.ModelAdmin):
    list_display = ('resident', 'position', 'term_start', 'term_end', 'status')
    list_filter = ('position', 'status')
    search_fields = ('resident__last_name', 'resident__first_name', 'employee_id')
