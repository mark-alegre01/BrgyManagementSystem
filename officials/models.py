from django.db import models
from django.conf import settings


class Official(models.Model):
    """Barangay official/staff member."""
    POSITION_CHOICES = [
        ('captain', 'Punong Barangay (Captain)'),
        ('kagawad', 'Sangguniang Barangay Member (Kagawad)'),
        ('secretary', 'Barangay Secretary'),
        ('treasurer', 'Barangay Treasurer'),
        ('sk_chairman', 'SK Chairperson'),
        ('sk_kagawad', 'SK Kagawad'),
        ('tanod', 'Barangay Tanod'),
        ('bhw', 'Barangay Health Worker (BHW)'),
        ('nutrition_scholar', 'Barangay Nutrition Scholar (BNS)'),
        ('day_care_worker', 'Day Care Worker'),
        ('lupon', 'Lupon Member'),
        ('clerk', 'Barangay Clerk'),
        ('staff', 'Barangay Staff'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_leave', 'On Leave'),
    ]

    resident = models.OneToOneField('residents.Resident', on_delete=models.CASCADE, related_name='official_record')
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='official_profile')
    position = models.CharField(max_length=30, choices=POSITION_CHOICES)
    committee = models.CharField(max_length=200, blank=True, help_text='Committee assignment')
    term_start = models.DateField()
    term_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    employee_id = models.CharField(max_length=50, blank=True, null=True, unique=True)
    is_active = models.BooleanField(default=True, help_text='Uncheck to soft-delete without losing records')

    # NOTE: fingerprint_template removed – use official.resident.fingerprint_template instead

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """Enforce limits on active official positions."""
        from django.core.exceptions import ValidationError
        
        if self.status == 'active':
            # Count other active officials for the same position
            active_count = Official.objects.filter(position=self.position, status='active')
            if self.pk:
                active_count = active_count.exclude(pk=self.pk)
            active_count = active_count.count()
            
            limits = {
                'captain': 1,
                'treasurer': 1,
                'secretary': 1,
                'kagawad': 7,
            }
            
            if self.position in limits:
                max_allowed = limits[self.position]
                if active_count >= max_allowed:
                    raise ValidationError({
                        'status': f"There can only be {max_allowed} active {self.get_position_display()} at a time."
                    })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def fingerprint_template(self):
        """Proxy to resident's fingerprint for backward compatibility."""
        return self.resident.fingerprint_template if self.resident else None

    @fingerprint_template.setter
    def fingerprint_template(self, value):
        """Proxy setter to resident's fingerprint."""
        if self.resident:
            self.resident.fingerprint_template = value
            self.resident.save()

    def __str__(self):
        return f"{self.resident.full_name} - {self.get_position_display()}"

    class Meta:
        ordering = ['position']
        verbose_name = 'Official'
        verbose_name_plural = 'Officials'


import uuid
from django.utils import timezone

class OfficialInvite(models.Model):
    """Model to track official invitations and onboarding."""
    STATUS_CHOICES = [
        ('pending_documents', 'Pending Documents'),
        ('pending_approval', 'Pending Approval'),
        ('pending_otp', 'Pending OTP'),
        ('activated', 'Activated'),
        ('rejected', 'Rejected'),
    ]

    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='sent_official_invites')
    
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    position = models.CharField(max_length=30, choices=Official.POSITION_CHOICES)
    phone_number = models.CharField(max_length=20)
    
    # Document Uploads
    appointment_letter = models.FileField(upload_to='official_docs/appointment/', null=True, blank=True)
    valid_id = models.FileField(upload_to='official_docs/id/', null=True, blank=True)
    
    # Approvals
    captain_approved = models.BooleanField(default=False)
    secretary_approved = models.BooleanField(default=False)
    
    # OTP Tracking
    otp_code = models.CharField(max_length=6, null=True, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_documents')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def is_otp_valid(self, code):
        if not self.otp_code or not self.otp_expires_at:
            return False
        if timezone.now() > self.otp_expires_at:
            return False
        return self.otp_code == code.strip()

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.get_position_display()} ({self.status})"


class OnboardingAuditLog(models.Model):
    """To track the exact steps of an official invite activation."""
    invite = models.ForeignKey(OfficialInvite, on_delete=models.CASCADE, related_name='logs')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
         return f"{self.invite.first_name} - {self.action} at {self.created_at}"
