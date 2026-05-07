from django.contrib import admin
from .models import Resident, Household, Purok

@admin.register(Purok)
class PurokAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)

@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ('household_no', 'purok', 'member_count')
    list_filter = ('purok',)
    search_fields = ('household_no', 'address')

@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'age', 'gender', 'purok', 'is_registered_voter', 'is_active')
    list_filter = ('gender', 'purok', 'is_registered_voter', 'is_active', 'is_pwd', 'is_senior_citizen')
    search_fields = ('first_name', 'last_name', 'middle_name')
    readonly_fields = ('created_at', 'updated_at')
