from django.db import models
from django.contrib.auth.models import AbstractUser, Group
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings


class Role(models.Model):
    """Lookup table for user roles."""
    name = models.CharField(max_length=30, unique=True)
    display_name = models.CharField(max_length=100)
    permission_level = models.IntegerField(
        default=3,
        help_text="1=Admin, 2=Staff, 3=Resident",
    )

    def __str__(self):
        return self.display_name

    class Meta:
        ordering = ['permission_level', 'name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'


class User(AbstractUser):
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    def get_permission_level(self):
        if self.is_superuser:
            return 1
        if self.role:
            return self.role.permission_level
        return 3

    def get_role_display(self):
        if self.is_superuser:
            return "Administrator"
        if self.role:
            return self.role.display_name
        return "Resident"


class UserProfile(models.Model):
    """Extended user profile – bridges User ↔ Resident."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile")
    resident = models.OneToOneField("residents.Resident", on_delete=models.SET_NULL, null=True, blank=True, related_name="user_profile")
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def role(self):
        return self.user.role.name if self.user.role else None

    @role.setter
    def role(self, value):
        try:
            role_obj = Role.objects.get(name=value)
            self.user.role = role_obj
            self.user.save()
        except Role.DoesNotExist:
            pass

    @property
    def avatar(self):
        return self.user.avatar

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
def assign_superuser_role(sender, instance, created, **kwargs):
    """Automatically assign Admin role to superusers."""
    if created and instance.is_superuser and not instance.role:
        try:
            admin_role = Role.objects.filter(models.Q(name='admin') | models.Q(name='captain')).first()
            if admin_role:
                instance.role = admin_role
                instance.save()
        except Exception:
            pass

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

from django.db.models.signals import pre_delete

@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def cleanup_resident_on_user_delete(sender, instance, **kwargs):
    """Ensure Resident record is deleted when User is deleted."""
    try:
        # Check if there was an associated resident profile
        # Use hasattr or try/except because profile might have been deleted already by CASCADE
        if hasattr(instance, 'profile') and instance.profile.resident:
            instance.profile.resident.delete()
    except Exception:
        pass
