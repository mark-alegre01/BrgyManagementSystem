from django.contrib import admin
from .models import Certificate

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('control_number', 'resident', 'cert_type', 'date_issued', 'amount_paid', 'status')
    list_filter = ('cert_type', 'status', 'date_issued')
    search_fields = ('control_number', 'resident__last_name', 'resident__first_name', 'purpose')
    readonly_fields = ('date_issued', 'created_at')
