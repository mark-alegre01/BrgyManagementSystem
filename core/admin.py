from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from .models import Role, UserProfile, SystemSettings
User = get_user_model()

# Unregister default User admin if already registered
try: admin.site.unregister(User)
except admin.sites.NotRegistered: pass

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    def get_role(self, obj):
        return obj.get_role_display()
    get_role.short_description = 'Role'

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('display_name', 'name', 'permission_level')
    search_fields = ('name', 'display_name')
    list_editable = ('permission_level',)

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('barangay_name', 'municipality', 'province')
