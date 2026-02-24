from django.contrib import admin
from .models import PhilSysVerificationAttempt


@admin.register(PhilSysVerificationAttempt)
class PhilSysVerificationAttemptAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "resident",
        "verification_method",
        "status",
        "philSys_number",
        "ip_address",
        "created_at",
    ]
    list_filter = [
        "status",
        "verification_method",
        "created_at",
    ]
    search_fields = [
        "user__username",
        "philSys_number",
        "ip_address",
    ]
    readonly_fields = [
        "created_at",
        "completed_at",
        "ip_address",
    ]
    ordering = ["-created_at"]
    date_hierarchy = "created_at"

    fieldsets = (
        ("User Information", {"fields": ("user", "resident")}),
        (
            "Verification Details",
            {
                "fields": (
                    "verification_method",
                    "status",
                    "philSys_number",
                    "philSys_card_number",
                )
            },
        ),
        (
            "Response Data",
            {"fields": ("response_data", "error_message"), "classes": ("collapse",)},
        ),
        (
            "Metadata",
            {
                "fields": ("ip_address", "created_at", "completed_at"),
                "classes": ("collapse",),
            },
        ),
    )
