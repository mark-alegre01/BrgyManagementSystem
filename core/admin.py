from django.contrib import admin
from .models import Role, UserProfile, SystemSettings

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'permission_level')
    search_fields = ('name', 'display_name')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'get_role', 'get_phone', 'has_fingerprint', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'resident__contact_number')

    def get_role(self, obj: UserProfile):
        return obj.role
    get_role.short_description = 'Role'

    def get_phone(self, obj: UserProfile):
        return obj.phone
    get_phone.short_description = 'Phone'

    def has_fingerprint(self, obj: UserProfile):
        return bool(obj.fingerprint_template)

    has_fingerprint.short_description = 'Fingerprint'

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('barangay_name', 'municipality', 'province')
