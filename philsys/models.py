from django.db import models
from django.contrib.auth.models import User


class PhilSysVerificationAttempt(models.Model):
    """Logs PhilSys verification attempts."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
    ]
    VERIFICATION_METHOD_CHOICES = [
        ("qr", "QR Code"),
        ("psn", "PSN"),
        ("biometric", "Biometric"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="philsys_attempts"
    )
    resident = models.ForeignKey(
        "residents.Resident",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="philsys_attempts",
    )
    philSys_number = models.CharField(max_length=12, blank=True, null=True)
    philSys_card_number = models.CharField(max_length=20, blank=True, null=True)
    verification_method = models.CharField(
        max_length=20, choices=VERIFICATION_METHOD_CHOICES
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    response_data = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "PhilSys Verification Attempt"
        verbose_name_plural = "PhilSys Verification Attempts"
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["status"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"Verification {self.id} - {self.user.username} - {self.status}"
