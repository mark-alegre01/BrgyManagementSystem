from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser
from django.conf import settings



class User(AbstractUser):
    ROLE_CHOICES = [
        ("captain", "Barangay Captain"),
        ("secretary", "Barangay Secretary"),
        ("treasurer", "Barangay Treasurer"),
        ("kagawad", "Kagawad"),
        ("sk_chairperson", "SK Chairperson"),
        ("lupong_member", "Lupon Member"),
        ("bhw", "Barangay BHW"),
        ("resident", "Resident"),
        ("admin", "Administrator"),
        ("staff", "Staff"),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="resident")

    def get_permission_level(self):
        level_1 = ['captain', 'secretary', 'treasurer', 'admin']
        level_2 = ['kagawad', 'sk_chairperson', 'bhw', 'lupong_member', 'staff']
        
        if self.role in level_1:
            return 1
        elif self.role in level_2:
            return 2
        else:
            return 3

class UserProfile(models.Model):
    """Extended user profile with role-based access."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    resident = models.OneToOneField("residents.Resident", on_delete=models.SET_NULL, null=True, blank=True, related_name="user_profile")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def role(self):
        return self.user.role
        
    @role.setter
    def role(self, value):
        self.user.role = value
        self.user.save()


    @property
    def middle_name(self):
        return self.resident.middle_name if self.resident else ""

    @middle_name.setter
    def middle_name(self, value):
        if self.resident:
            self.resident.middle_name = value
            self.resident.save()

    @property
    def phone(self):
        return self.resident.contact_number if self.resident else ""

    @phone.setter
    def phone(self, value):
        if self.resident:
            self.resident.contact_number = value
            self.resident.save()

    @property
    def philSys_id(self):
        return self.resident.philSys_number if self.resident else None

    @philSys_id.setter
    def philSys_id(self, value):
        if self.resident:
            self.resident.philSys_number = value
            self.resident.save()

    @property
    def is_philsys_verified(self):
        return self.resident.is_philsys_verified if self.resident else False

    @is_philsys_verified.setter
    def is_philsys_verified(self, value):
        if self.resident:
            self.resident.is_philsys_verified = value
            self.resident.save()

    @property
    def philsys_verified_at(self):
        return self.resident.philsys_verified_at if self.resident else None

    @philsys_verified_at.setter
    def philsys_verified_at(self, value):
        if self.resident:
            self.resident.philsys_verified_at = value
            self.resident.save()

    @property
    def fingerprint_template(self):
        return self.resident.fingerprint_template if self.resident else None

    @fingerprint_template.setter
    def fingerprint_template(self, value):
        if self.resident:
            self.resident.fingerprint_template = value
            self.resident.save()

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.user.get_role_display()}"

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

    def __str__(self):
        return self.barangay_name

    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"


class Notification(models.Model):
    """In-app notification for a specific user."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications'
    )
    message = models.TextField()
    link = models.CharField(max_length=300, blank=True, help_text='Optional URL path for the notification')
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message[:50]}"

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def assign_user_group(sender, instance, created, **kwargs):
    """Assign users to proper groups based on permission level."""
    level = instance.get_permission_level()
    group_name = None
    if level == 1:
        group_name = "Admin"
    elif level == 2:
        group_name = "Staff"
    elif level == 3:
        group_name = "Resident"
        
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        # Clear existing groups to strictly enforce current role level
        instance.groups.clear()
        instance.groups.add(group)
