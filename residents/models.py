from django.db import models
from datetime import date


class Household(models.Model):
    """Household/family unit."""

    household_no = models.CharField(max_length=50, unique=True)
    address = models.TextField()
    purok = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Household #{self.household_no} - {self.purok}"

    @property
    def member_count(self):
        return self.members.count()

    @property
    def head(self):
        return self.members.filter(is_household_head=True).first()

    class Meta:
        ordering = ["household_no"]


class Resident(models.Model):
    """Barangay resident record."""

    GENDER_CHOICES = [("M", "Male"), ("F", "Female")]
    CIVIL_STATUS_CHOICES = [
        ("single", "Single"),
        ("married", "Married"),
        ("widowed", "Widowed"),
        ("separated", "Separated"),
        ("divorced", "Divorced"),
    ]
    PHILSYS_VERIFICATION_METHOD_CHOICES = [
        ("qr", "QR Code"),
        ("psn", "PSN"),
        ("biometric", "Biometric"),
    ]

    # Personal info
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    suffix = models.CharField(max_length=20, blank=True)
    birthdate = models.DateField()
    birthplace = models.CharField(max_length=200, blank=True)
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    civil_status = models.CharField(
        max_length=20, choices=CIVIL_STATUS_CHOICES, default="single"
    )
    nationality = models.CharField(max_length=100, default="Filipino")
    religion = models.CharField(max_length=100, blank=True)
    occupation = models.CharField(max_length=200, blank=True)

    # Contact
    contact_number = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)

    # Address
    address = models.TextField()
    purok = models.CharField(max_length=100, blank=True)

    # Household
    household = models.ForeignKey(
        Household,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    is_household_head = models.BooleanField(default=False)

    # PhilSys Integration
    philSys_number = models.CharField(
        max_length=12, blank=True, null=True, verbose_name="PhilSys Number (PSN)"
    )
    philSys_card_number = models.CharField(
        max_length=20, blank=True, null=True, verbose_name="PhilSys Card Number (PCN)"
    )
    is_philsys_verified = models.BooleanField(default=False)
    philsys_verified_at = models.DateTimeField(blank=True, null=True)
    philsys_verification_method = models.CharField(
        max_length=20,
        choices=PHILSYS_VERIFICATION_METHOD_CHOICES,
        blank=True,
        null=True,
    )

    # Status
    is_registered_voter = models.BooleanField(default=False)
    is_pwd = models.BooleanField(default=False, verbose_name="Person with Disability")
    is_senior_citizen = models.BooleanField(default=False)
    is_4ps_member = models.BooleanField(default=False, verbose_name="4Ps Member")
    is_official = models.BooleanField(default=False, verbose_name="Barangay Functionary")

    # Photo
    photo = models.ImageField(upload_to="residents/photos/", blank=True, null=True)

    # Biometrics
    fingerprint_template = models.TextField(blank=True, null=True, help_text="Base64 encoded fingerprint template")

    # Metadata
    is_active = models.BooleanField(default=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def display_occupation(self):
        """Return official position if functionary, else regular occupation."""
        if self.is_official and hasattr(self, 'official_record'):
            return self.official_record.get_position_display()
        return self.occupation or "Unemployed"

    def __str__(self):
        name = f"{self.last_name}, {self.first_name}"
        if self.middle_name:
            name += f" {self.middle_name}"
        if self.suffix:
            name += f" {self.suffix}"
        return name

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        if self.suffix:
            parts.append(self.suffix)
        return " ".join(p for p in parts if p)

    @property
    def age(self):
        today = date.today()
        return (
            today.year
            - self.birthdate.year
            - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))
        )

    @property
    def age_group(self):
        age = self.age
        if age < 1:
            return "Infant"
        elif age <= 5:
            return "Early Childhood"
        elif age <= 12:
            return "Child"
        elif age <= 17:
            return "Teenager"
        elif age <= 24:
            return "Young Adult"
        elif age <= 59:
            return "Adult"
        else:
            return "Senior Citizen"

    class Meta:
        ordering = ["last_name", "first_name"]
        verbose_name = "Resident"
        verbose_name_plural = "Residents"
