from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Extended user profile with role-based access."""

    ROLE_CHOICES = [
        ("captain", "Barangay Captain"),
        ("secretary", "Barangay Secretary"),
        ("treasurer", "Barangay Treasurer"),
        ("kagawad", "Kagawad"),
        ("sk_chairperson", "SK Chairperson"),
        ("lupong_member", "Lupon Member"),
        ("resident", "Resident"),
        ("admin", "Administrator"),
        ("staff", "Staff"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    resident = models.OneToOneField("residents.Resident", on_delete=models.SET_NULL, null=True, blank=True, related_name="user_profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="resident")
    middle_name = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    philSys_id = models.CharField(max_length=50, blank=True, null=True, unique=True)
    is_philsys_verified = models.BooleanField(default=False)
    philsys_verified_at = models.DateTimeField(blank=True, null=True)
    fingerprint_template = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_role_display()}"

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"


class SystemSettings(models.Model):
    """Barangay system settings."""

    barangay_name = models.CharField(max_length=200, default="Barangay Sample")
    municipality = models.CharField(max_length=200, default="Municipality of Sample")
    province = models.CharField(max_length=200, default="Province of Sample")
    region = models.CharField(max_length=200, default="Region Sample")
    barangay_logo = models.ImageField(upload_to="settings/", blank=True, null=True)
    captain_name = models.CharField(max_length=200, blank=True)
    secretary_name = models.CharField(max_length=200, blank=True)
    treasurer_name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.barangay_name

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"
