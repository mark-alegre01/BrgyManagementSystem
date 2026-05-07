from django.contrib import admin
from .models import AttendanceLog, FaceEncoding

@admin.register(FaceEncoding)
class FaceEncodingAdmin(admin.ModelAdmin):
    list_display = ('resident', 'enrolled_at')

@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ('official', 'date', 'time_in', 'time_out', 'status', 'method')
    list_filter = ('date', 'status', 'method')
    search_fields = ('official__resident__last_name', 'official__resident__first_name')
