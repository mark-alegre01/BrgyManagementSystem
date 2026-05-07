from django.contrib import admin
from .models import Certificate

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('control_number', 'resident', 'get_cert_type', 'date_issued', 'amount_paid', 'status')
    list_filter = ('status', 'date_issued')
    search_fields = ('control_number', 'resident__last_name', 'resident__first_name')
    readonly_fields = ('date_issued', 'created_at')

    @admin.display(description='Certificate Type')
    def get_cert_type(self, obj):
        return obj.get_cert_type_display() or '—'
