from django.db import models
import json


class FaceEncoding(models.Model):
    """Stored face encoding for an official/staff member."""
    official = models.OneToOneField('officials.Official', on_delete=models.CASCADE, related_name='face_encoding')
    encoding_data = models.TextField(help_text='JSON-encoded face encoding array')
    photo = models.ImageField(upload_to='face_encodings/')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def set_encoding(self, encoding_array):
        self.encoding_data = json.dumps(encoding_array.tolist() if hasattr(encoding_array, 'tolist') else list(encoding_array))

    def get_encoding(self):
        import numpy as np
        return np.array(json.loads(self.encoding_data))

    def __str__(self):
        return f"Face Encoding - {self.official}"


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
