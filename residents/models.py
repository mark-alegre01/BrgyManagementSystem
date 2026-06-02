from django.db import models
from datetime import date


class Purok(models.Model):
    """Purok/zone lookup table for normalized queries."""
    name = models.CharField(max_length=100, unique=True)
    
    # Geo coordinates for mapping
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']
        verbose_name = 'Purok'
        verbose_name_plural = 'Puroks'


class Household(models.Model):
    """Household/family unit."""

    household_no = models.CharField(max_length=50, unique=True)
    address = models.TextField()
    purok = models.ForeignKey(
        Purok,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='households',
    )
    # Geo coordinates for mapping
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Household #{self.household_no} - {self.purok or 'N/A'}"

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
    purok = models.ForeignKey(
        Purok,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='residents',
    )

    # Household
    HOUSEHOLD_RELATIONSHIP_CHOICES = [
        ("head", "Head"),
        ("spouse", "Spouse"),
        ("child", "Child"),
        ("parent", "Parent"),
        ("sibling", "Sibling"),
        ("grandchild", "Grandchild"),
        ("grandparent", "Grandparent"),
        ("other", "Other Relative"),
    ]

    household = models.ForeignKey(
        Household,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    is_household_head = models.BooleanField(default=False)
    household_relationship = models.CharField(
        max_length=20, 
        choices=HOUSEHOLD_RELATIONSHIP_CHOICES, 
        blank=True, 
        null=True,
        verbose_name="Relationship to Head"
    )
    parent_member = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='children_members',
        help_text="Custom parent relationship for interactive family tree"
    )

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
    is_indigent = models.BooleanField(default=False)
    is_solo_parent = models.BooleanField(default=False)
    is_official = models.BooleanField(default=False, verbose_name="Barangay Functionary")

    # Photo
    photo = models.ImageField(upload_to="residents/photos/", blank=True, null=True)

    # Biometrics (single source of truth for fingerprint data)
    fingerprint_template = models.TextField(blank=True, null=True, help_text="Base64 encoded fingerprint template")
    fingerprint_id = models.IntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text="0-based template page index in the R307/AS608 module (0 .. capacity-1)",
    )

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
        constraints = [
            models.UniqueConstraint(
                fields=['first_name', 'middle_name', 'last_name', 'suffix', 'birthdate'],
                name='unique_resident_name_birthdate'
            )
        ]


import uuid
import random
import string

def generate_reference_number():
    """Generate a unique tracking reference number (e.g. BRGY-2026-X1Y2Z3)."""
    current_year = date.today().year
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BRGY-{current_year}-{random_str}"

class ResidentRegistration(models.Model):
    """Temporary storage for resident registration before verification."""
    
    STATUS_CHOICES = [
        ("pending", "Pending Verification"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]
    
    # Tracking
    reference_number = models.CharField(max_length=20, unique=True, default=generate_reference_number)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    
    # Step 1: Personal Info
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    suffix = models.CharField(max_length=20, blank=True)
    birthdate = models.DateField()
    birthplace = models.CharField(max_length=200, blank=True)
    gender = models.CharField(max_length=1, choices=[("M", "Male"), ("F", "Female")])
    civil_status = models.CharField(max_length=20, default="single")
    nationality = models.CharField(max_length=100, default="Filipino")
    religion = models.CharField(max_length=100, blank=True)
    highest_education = models.CharField(max_length=100, blank=True)
    occupation = models.CharField(max_length=200, blank=True)
    
    # Step 2: Contact & Address
    mobile_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    house_number = models.CharField(max_length=100, blank=True)
    street = models.CharField(max_length=100, blank=True)
    purok = models.CharField(max_length=100, blank=True)
    barangay = models.CharField(max_length=100, default="Sample Barangay")
    municipality = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, default="Cagayan de Oro")
    zip_code = models.CharField(max_length=10, default="9000")
    years_of_residency = models.IntegerField(default=0)
    philSys_number = models.CharField(max_length=12, blank=True, null=True)
    
    # Step 3: Household & Classification
    is_joining_household = models.BooleanField(default=False)
    household_number = models.CharField(max_length=50, blank=True, null=True)
    is_pwd = models.BooleanField(default=False)
    is_senior_citizen = models.BooleanField(default=False)
    is_4ps_member = models.BooleanField(default=False)
    is_sole_parent = models.BooleanField(default=False)
    is_registered_voter = models.BooleanField(default=False)

    
    # Guardian (Dynamic for Minors)
    guardian_name = models.CharField(max_length=200, blank=True, null=True)
    guardian_relationship = models.CharField(max_length=100, blank=True, null=True)
    guardian_contact = models.CharField(max_length=20, blank=True, null=True)
    guardian_id_number = models.CharField(max_length=50, blank=True, null=True)
    
    # Step 4: Account & Documents
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128)
    
    # File Uploads
    photo = models.ImageField(upload_to="registrations/photos/", blank=True, null=True)
    id_card = models.ImageField(upload_to="registrations/ids/", blank=True, null=True)
    birth_certificate = models.ImageField(upload_to="registrations/birth_certs/", blank=True, null=True)
    proof_of_residency = models.ImageField(upload_to="registrations/residency/", blank=True, null=True)
    
    # Privacy
    data_privacy_consent = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.reference_number} - {self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "Resident Registration"
        verbose_name_plural = "Resident Registrations"
        ordering = ["-created_at"]

from django.db.models.signals import pre_delete
from django.dispatch import receiver

@receiver(pre_delete, sender=Resident)
def cleanup_user_on_resident_delete(sender, instance, **kwargs):
    """Ensure User account is deleted when Resident record is deleted."""
    try:
        # Using pre_delete ensures we can still access the related user_profile
        if hasattr(instance, 'user_profile') and instance.user_profile and instance.user_profile.user:
            instance.user_profile.user.delete()
    except Exception:
        pass
@receiver(pre_delete, sender=Resident)
def delete_fingerprint_from_sensor(sender, instance, **kwargs):
    """Attempt to delete fingerprint from ESP32 sensor when resident is deleted."""
    if instance.fingerprint_id is not None:
        from core.utils.biometric_discovery import get_esp32_base_url
        import requests
        esp32_base_url = get_esp32_base_url()
        try:
            requests.post(f"{esp32_base_url}/delete-fingerprint?id={instance.fingerprint_id}", timeout=2, proxies={'http': None, 'https': None})
        except Exception:
            # Silent fail if ESP32 is offline during deletion
            pass
