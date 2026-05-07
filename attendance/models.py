from django.db import models
import json


class Biometric(models.Model):
    """
    Consolidated biometric record for a resident.
    Replaces the duplicated fingerprint_template on RESIDENT/OFFICIAL
    and the formerly separate FaceEncoding table.
    """
    resident = models.OneToOneField(
        'residents.Resident',
        on_delete=models.CASCADE,
        related_name='biometric',
    )
    # Face recognition
    face_encoding_data = models.TextField(
        blank=True, null=True,
        help_text='JSON-encoded face encoding array',
    )
    face_photo = models.ImageField(upload_to='biometrics/face/', blank=True, null=True)
    # Fingerprint
    fingerprint_template = models.TextField(
        blank=True, null=True,
        help_text='Base64-encoded fingerprint template',
    )
    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_face_encoding(self, encoding_array):
        self.face_encoding_data = json.dumps(
            encoding_array.tolist() if hasattr(encoding_array, 'tolist') else list(encoding_array)
        )

    def get_face_encoding(self):
        import numpy as np
        return np.array(json.loads(self.face_encoding_data))

    def __str__(self):
        return f"Biometric record – {self.resident}"

    class Meta:
        verbose_name = 'Biometric'
        verbose_name_plural = 'Biometrics'


# ---------------------------------------------------------------------------
# Legacy alias so existing imports of FaceEncoding don't hard-break immediately
# TODO: remove after all call sites updated
FaceEncoding = Biometric


class AttendanceLog(models.Model):
    """Daily attendance record for officials/staff."""
    METHOD_CHOICES = [
        ('face', 'Face Recognition'),
        ('manual', 'Manual Entry'),
        ('biometric', 'Biometric/Fingerprint'),
    ]
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('late', 'Late'),
        ('absent', 'Absent'),
        ('half_day', 'Half Day'),
        ('on_leave', 'On Leave'),
    ]

    official = models.ForeignKey('officials.Official', on_delete=models.CASCADE, related_name='attendance_logs')
    date = models.DateField()
    time_in = models.TimeField(null=True, blank=True)
    time_out = models.TimeField(null=True, blank=True)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='manual')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='present')
    remarks = models.TextField(blank=True)
    photo_in = models.ImageField(upload_to='attendance/photos/', blank=True, null=True)
    photo_out = models.ImageField(upload_to='attendance/photos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.official} - {self.date} ({self.get_status_display()})"

    @property
    def hours_worked(self):
        if self.time_in and self.time_out:
            from datetime import datetime, timedelta
            dt_in = datetime.combine(self.date, self.time_in)
            dt_out = datetime.combine(self.date, self.time_out)
            diff = dt_out - dt_in
            return round(diff.total_seconds() / 3600, 2)
        return 0

    class Meta:
        ordering = ['-date', 'official']
        unique_together = ['official', 'date']
        verbose_name = 'Attendance Log'
        verbose_name_plural = 'Attendance Logs'
