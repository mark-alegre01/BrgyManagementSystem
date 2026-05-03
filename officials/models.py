from django.db import models
from django.contrib.auth.models import User


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
        ('health_worker', 'Barangay Health Worker (BHW)'),
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
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='official_profile')
    position = models.CharField(max_length=30, choices=POSITION_CHOICES)
    committee = models.CharField(max_length=200, blank=True, help_text='Committee assignment')
    term_start = models.DateField()
    term_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    employee_id = models.CharField(max_length=50, blank=True, null=True, unique=True)
    
    # Biometrics
    fingerprint_template = models.TextField(blank=True, null=True, help_text="Base64 encoded fingerprint template")

    created_at = models.DateTimeField(auto_now_add=True)

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

    def __str__(self):
        return f"{self.resident.full_name} - {self.get_position_display()}"

    class Meta:
        ordering = ['position']
        verbose_name = 'Official'
        verbose_name_plural = 'Officials'
