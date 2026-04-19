from django.db import models
from django.conf import settings
from residents.models import Resident

class Appointment(models.Model):
    PURPOSE_CHOICES = [
        ('certification', 'Request Certification'),
        ('clearance', 'Barangay Clearance'),
        ('indigency', 'Certificate of Indigency'),
        ('meeting', 'Meeting with Officials'),
        ('complaint', 'File a Complaint/Blotter'),
        ('business', 'Business Permit'),
        ('other', 'Other Purpose'),
    ]

    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('no_show', 'No Show'),
    ]

    resident = models.ForeignKey(Resident, on_delete=models.CASCADE, related_name='appointments')
    purpose = models.CharField(max_length=50, choices=PURPOSE_CHOICES)
    specification = models.TextField(blank=True, help_text="Specific details about the request")
    appointment_date = models.DateField()
    appointment_time = models.TimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['appointment_date', 'appointment_time']
        verbose_name = "Appointment"
        verbose_name_plural = "Appointments"

    def __str__(self):
        return f"{self.resident.full_name} - {self.get_purpose_display()} on {self.appointment_date}"
