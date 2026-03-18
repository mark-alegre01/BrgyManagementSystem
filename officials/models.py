from django.db import models


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
        ('health_worker', 'Barangay Health Worker'),
        ('nutrition_scholar', 'Barangay Nutrition Scholar'),
        ('day_care_worker', 'Day Care Worker'),
        ('lupon', 'Lupon Member'),
        ('staff', 'Staff'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('on_leave', 'On Leave'),
    ]

    resident = models.OneToOneField('residents.Resident', on_delete=models.CASCADE, related_name='official_record')
    position = models.CharField(max_length=30, choices=POSITION_CHOICES)
    committee = models.CharField(max_length=200, blank=True, help_text='Committee assignment')
    term_start = models.DateField()
    term_end = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    salary = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    employee_id = models.CharField(max_length=50, blank=True, unique=True)
    
    # Biometrics
    fingerprint_template = models.TextField(blank=True, null=True, help_text="Base64 encoded fingerprint template")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.resident.full_name} - {self.get_position_display()}"

    class Meta:
        ordering = ['position']
        verbose_name = 'Official'
        verbose_name_plural = 'Officials'
