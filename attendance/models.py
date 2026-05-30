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


class ShiftConfiguration(models.Model):
    DAY_CHOICES = [
        ('mon', 'Monday'),
        ('tue', 'Tuesday'),
        ('wed', 'Wednesday'),
        ('thu', 'Thursday'),
        ('fri', 'Friday'),
        ('sat', 'Saturday'),
        ('sun', 'Sunday'),
    ]
    day = models.CharField(max_length=3, choices=DAY_CHOICES, unique=True)
    am_in = models.TimeField(default='08:00')
    am_out = models.TimeField(default='12:00')
    pm_in = models.TimeField(default='13:00')
    pm_out = models.TimeField(default='17:00')
    is_day_off = models.BooleanField(default=False)
    grace_period = models.IntegerField(default=15)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_day_display()} Configuration"

    class Meta:
        verbose_name = 'Shift Configuration'
        verbose_name_plural = 'Shift Configurations'


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
    
    # Legacy fields (kept for backward compatibility during transition)
    time_in = models.TimeField(null=True, blank=True)
    time_out = models.TimeField(null=True, blank=True)
    
    # New Morning/Afternoon fields
    am_in = models.TimeField(null=True, blank=True)
    am_out = models.TimeField(null=True, blank=True)
    pm_in = models.TimeField(null=True, blank=True)
    pm_out = models.TimeField(null=True, blank=True)
    
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
        total_seconds = 0
        from datetime import datetime
        
        # AM Session
        if self.am_in and self.am_out:
            dt_in = datetime.combine(self.date, self.am_in)
            dt_out = datetime.combine(self.date, self.am_out)
            total_seconds += (dt_out - dt_in).total_seconds()
        # PM Session
        if self.pm_in and self.pm_out:
            dt_in = datetime.combine(self.date, self.pm_in)
            dt_out = datetime.combine(self.date, self.pm_out)
            total_seconds += (dt_out - dt_in).total_seconds()
            
        if total_seconds > 0:
            return round(total_seconds / 3600, 2)
            
        # Fallback to legacy fields if new fields are empty
        if self.time_in and self.time_out:
            dt_in = datetime.combine(self.date, self.time_in)
            dt_out = datetime.combine(self.date, self.time_out)
            return round((dt_out - dt_in).total_seconds() / 3600, 2)
            
        return 0

    class Meta:
        ordering = ['-date', 'official']
        unique_together = ['official', 'date']
        verbose_name = 'Attendance Log'
        verbose_name_plural = 'Attendance Logs'


class SpecialDate(models.Model):
    """Custom holidays or specific non-working dates."""
    date = models.DateField(unique=True)
    is_day_off = models.BooleanField(default=True)
    description = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.date} - {'Day Off' if self.is_day_off else 'Working Day'}"

    class Meta:
        ordering = ['-date']
        verbose_name = 'Special Date'
        verbose_name_plural = 'Special Dates'


class WorkSchedule(models.Model):
    """Customizable work schedule per official per date."""
    SHIFT_CHOICES = [
        ('regular', 'Regular (8 AM - 5 PM)'),
        ('morning', 'Morning Shift (8 AM - 12 PM)'),
        ('afternoon', 'Afternoon Shift (1 PM - 5 PM)'),
        ('night', 'Night Shift (10 PM - 6 AM)'),
        ('day_off', 'Day Off / Rest Day'),
        ('leave', 'On Leave'),
    ]

    official = models.ForeignKey('officials.Official', on_delete=models.CASCADE, related_name='work_schedules')
    date = models.DateField()
    shift_type = models.CharField(max_length=20, choices=SHIFT_CHOICES, default='regular')
    
    # Optional override times (if a shift needs custom hours)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    
    notes = models.CharField(max_length=255, blank=True, help_text="Reason for leave, extra info, etc.")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.official} - {self.date} ({self.get_shift_type_display()})"

    def save(self, *args, **kwargs):
        # Auto-set default times based on shift type if not provided
        from datetime import time
        if not self.start_time or not self.end_time:
            if self.shift_type == 'regular':
                self.start_time = time(8, 0)
                self.end_time = time(17, 0)
            elif self.shift_type == 'morning':
                self.start_time = time(8, 0)
                self.end_time = time(12, 0)
            elif self.shift_type == 'afternoon':
                self.start_time = time(13, 0)
                self.end_time = time(17, 0)
            elif self.shift_type == 'night':
                self.start_time = time(22, 0)
                self.end_time = time(6, 0)
            elif self.shift_type in ['day_off', 'leave']:
                self.start_time = None
                self.end_time = None
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['date', 'official']
        unique_together = ['official', 'date']
        verbose_name = 'Work Schedule'
        verbose_name_plural = 'Work Schedules'
