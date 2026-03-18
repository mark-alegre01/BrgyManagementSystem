from django.contrib import admin
from .models import UserProfile, SystemSettings

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'phone', 'has_fingerprint', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')

    def has_fingerprint(self, obj: UserProfile):
        return bool(obj.fingerprint_template)

    has_fingerprint.short_description = 'Fingerprint'

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('barangay_name', 'municipality', 'province')
