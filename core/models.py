from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    """Extended user profile with role-based access."""
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('secretary', 'Barangay Secretary'),
        ('treasurer', 'Barangay Treasurer'),
        ('staff', 'Staff'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_role_display()}"

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'


class SystemSettings(models.Model):
    """Barangay system settings."""
    barangay_name = models.CharField(max_length=200, default='Barangay Sample')
    municipality = models.CharField(max_length=200, default='Municipality of Sample')
    province = models.CharField(max_length=200, default='Province of Sample')
    region = models.CharField(max_length=200, default='Region Sample')
    barangay_logo = models.ImageField(upload_to='settings/', blank=True, null=True)
    captain_name = models.CharField(max_length=200, blank=True)
    secretary_name = models.CharField(max_length=200, blank=True)
    treasurer_name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.barangay_name

    class Meta:
        verbose_name = 'System Settings'
        verbose_name_plural = 'System Settings'
