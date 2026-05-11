from django.contrib import admin
from .models import Official

@admin.register(Official)
class OfficialAdmin(admin.ModelAdmin):
    list_display = ('resident', 'position', 'status', 'term_start', 'term_end', 'user')
    list_filter = ('status', 'position', 'term_start')
    search_fields = ('resident__last_name', 'resident__first_name', 'employee_id', 'user__username')
    list_per_page = 20
