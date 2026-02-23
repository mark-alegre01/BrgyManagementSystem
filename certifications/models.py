from django.db import models
from django.contrib.auth.models import User


class Certificate(models.Model):
    """Certificate / clearance issued by the barangay."""
    TYPE_CHOICES = [
        ('clearance', 'Barangay Clearance'),
        ('residency', 'Certificate of Residency'),
        ('indigency', 'Certificate of Indigency'),
        ('good_moral', 'Good Moral Certificate'),
        ('business_permit', 'Business Permit/Clearance'),
        ('comelec', 'COMELEC Certificate'),
        ('cedula', 'Community Tax Certificate'),
        ('late_registration', 'Certificate of Late Registration'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('issued', 'Issued'),
        ('cancelled', 'Cancelled'),
    ]

    cert_type = models.CharField(max_length=30, choices=TYPE_CHOICES)
    control_number = models.CharField(max_length=50, unique=True)
    resident = models.ForeignKey('residents.Resident', on_delete=models.CASCADE, related_name='certificates')
    purpose = models.TextField()
    date_issued = models.DateField(auto_now_add=True)

    # For business permit
    business_name = models.CharField(max_length=200, blank=True)
    business_address = models.TextField(blank=True)
    business_type = models.CharField(max_length=200, blank=True)

    # Payment
    or_number = models.CharField(max_length=50, blank=True, verbose_name='OR Number')
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='issued')
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='certificates_issued')

    # Document
    pdf_file = models.FileField(upload_to='certificates/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_cert_type_display()} - {self.control_number}"

    class Meta:
        ordering = ['-date_issued']
        verbose_name = 'Certificate'
        verbose_name_plural = 'Certificates'
