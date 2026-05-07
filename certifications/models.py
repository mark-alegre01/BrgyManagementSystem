from django.db import models
from django.conf import settings
from decimal import Decimal


def generate_tracking_code():
    """Generate a random 9-character alphanumeric tracking code."""
    import string
    import random
    chars = string.ascii_uppercase + string.digits
    return "".join(random.choices(chars, k=9))


class Certificate(models.Model):
    """
    Certificate / clearance issued by the barangay.

    cert_type, purpose, and status are no longer stored here directly —
    they are read from the linked CertificateRequest to avoid duplication.
    Access via: certificate.request.cert_type / .purpose / .status
    """
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

    # Links
    resident = models.ForeignKey(
        'residents.Resident',
        on_delete=models.CASCADE,
        related_name='certificates',
    )
    # FK back to the request that originated this certificate
    certificate_request = models.OneToOneField(
        'CertificateRequest',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='issued_certificate',
    )

    control_number = models.CharField(max_length=50, unique=True)
    date_issued = models.DateField(auto_now_add=True)

    # For business permit
    business_name = models.CharField(max_length=200, blank=True)
    business_address = models.TextField(blank=True)
    business_type = models.CharField(max_length=200, blank=True)

    # For late registration of birth
    child_name = models.CharField(max_length=200, blank=True)
    child_birth_date = models.DateField(null=True, blank=True)
    child_birth_place = models.CharField(max_length=200, blank=True)
    father_name = models.CharField(max_length=200, blank=True)
    mother_name = models.CharField(max_length=200, blank=True)

    # Status (kept here so a certificate can be cancelled independently of the request)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='issued')
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='certificates_issued',
    )

    # Document
    pdf_file = models.FileField(upload_to='certificates/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # -----------------------------------------------------------------
    # Delegated properties – read from linked request to avoid duplication
    # -----------------------------------------------------------------
    @property
    def cert_type(self):
        return self.certificate_request.cert_type if self.certificate_request else None

    @property
    def purpose(self):
        return self.certificate_request.purpose if self.certificate_request else ''

    @property
    def or_number(self):
        """
        OR number lives exclusively in OfficialReceipt.
        Traverse: certificate → request → payment → official_receipt.
        """
        try:
            return self.certificate_request.payment.official_receipt.or_number
        except Exception:
            return None

    @property
    def amount_paid(self):
        """Payment amount via the linked payment record."""
        try:
            return self.certificate_request.payment.amount
        except Exception:
            return 0

    def get_cert_type_display(self):
        if self.cert_type:
            mapping = dict(self.TYPE_CHOICES)
            return mapping.get(self.cert_type, self.cert_type)
        return ''

    def __str__(self):
        return f"{self.get_cert_type_display()} - {self.control_number}"

    class Meta:
        ordering = ['-date_issued', '-id']
        verbose_name = 'Certificate'
        verbose_name_plural = 'Certificates'


class Cedula(models.Model):
    """Specific details for Community Tax Certificate (Cedula)."""
    TAXPAYER_TYPES = [
        ('individual', 'Individual'),
        ('corporation', 'Corporation'),
    ]

    certificate = models.OneToOneField(Certificate, on_delete=models.CASCADE, related_name='cedula_details')
    ctc_number = models.CharField(max_length=50, unique=True, verbose_name='CTC Number')
    taxpayer_type = models.CharField(max_length=20, choices=TAXPAYER_TYPES, default='individual')

    # Personal Info (matching official form)
    place_of_issue = models.CharField(max_length=200)
    height = models.CharField(max_length=20, blank=True, help_text="e.g. 170 cm")
    weight = models.CharField(max_length=20, blank=True, help_text="e.g. 65 kg")

    # Financial Info - Raw Taxable Amounts
    raw_taxable_property = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name='Taxable Property Value')
    raw_taxable_business = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name='Taxable Gross Receipts')
    raw_taxable_income = models.DecimalField(max_digits=15, decimal_places=2, default=0.00, verbose_name='Taxable Annual Income')

    # Calculated Tax Amounts
    basic_tax = models.DecimalField(max_digits=10, decimal_places=2, default=5.00)
    additional_tax_property = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Additional Tax (Property)')
    additional_tax_business = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Additional Tax (Business)')
    additional_tax_income = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name='Additional Tax (Income)')

    interest = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def total_additional_tax(self):
        def to_d(val):
            if val is None: return Decimal('0.00')
            try:
                return Decimal(str(val))
            except:
                return Decimal('0.00')

        prop = to_d(self.additional_tax_property)
        bus = to_d(self.additional_tax_business)
        inc = to_d(self.additional_tax_income)
        return prop + bus + inc

    @property
    def total_amount(self):
        def to_d(val):
            if val is None: return Decimal('0.00')
            try:
                return Decimal(str(val))
            except:
                return Decimal('0.00')

        basic = to_d(self.basic_tax)
        interest = to_d(self.interest)
        add_tax = self.total_additional_tax

        if self.taxpayer_type == 'individual':
            cap = Decimal('5000.00')
        else:
            cap = Decimal('10000.00')

        capped_additional_tax = add_tax
        if add_tax > cap:
            capped_additional_tax = cap

        return basic + capped_additional_tax + interest

    def save(self, *args, **kwargs):
        if not self.basic_tax or self.basic_tax == 0:
            self.basic_tax = Decimal('5.00') if self.taxpayer_type == 'individual' else Decimal('500.00')

        if self.taxpayer_type == 'individual':
            if not self.additional_tax_property and self.raw_taxable_property:
                self.additional_tax_property = (self.raw_taxable_property / 1000).quantize(Decimal('0.01'))
            if not self.additional_tax_business and self.raw_taxable_business:
                self.additional_tax_business = (self.raw_taxable_business / 1000).quantize(Decimal('0.01'))
            if not self.additional_tax_income and self.raw_taxable_income:
                self.additional_tax_income = (self.raw_taxable_income / 1000).quantize(Decimal('0.01'))
        else:
            if not self.additional_tax_property and self.raw_taxable_property:
                self.additional_tax_property = ((self.raw_taxable_property / 5000) * 2).quantize(Decimal('0.01'))
            if not self.additional_tax_business and self.raw_taxable_business:
                self.additional_tax_business = ((self.raw_taxable_business / 5000) * 2).quantize(Decimal('0.01'))

        # Synchronize payment amount – traverse via the request's payment
        try:
            payment = self.certificate.certificate_request.payment
            if payment:
                payment.amount = self.total_amount
                payment.save(update_fields=['amount'])
        except Exception:
            pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Cedula ({self.get_taxpayer_type_display()}) {self.ctc_number} - {self.certificate.resident}"

    class Meta:
        verbose_name = 'Cedula'
        verbose_name_plural = 'Cedulas'


class CertificateRequest(models.Model):
    """A resident's request for a barangay certificate."""

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('issued', 'Issued'),
        ('rejected', 'Rejected'),
    ]

    resident = models.ForeignKey(
        'residents.Resident',
        on_delete=models.CASCADE,
        related_name='certificate_requests',
    )
    tracking_code = models.CharField(max_length=20, unique=True, default=generate_tracking_code)
    cert_type = models.CharField(max_length=30, choices=Certificate.TYPE_CHOICES)
    purpose = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Payment integration
    payment = models.OneToOneField(
        'payments.Payment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='certificate_request'
    )

    # Specific details for the request
    # Business
    business_name = models.CharField(max_length=200, blank=True)
    business_address = models.TextField(blank=True)
    business_type = models.CharField(max_length=200, blank=True)

    # Cedula
    taxpayer_type = models.CharField(max_length=20, blank=True)
    place_of_issue = models.CharField(max_length=200, blank=True)
    height = models.CharField(max_length=20, blank=True)
    weight = models.CharField(max_length=20, blank=True)
    raw_taxable_property = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    raw_taxable_business = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)
    raw_taxable_income = models.DecimalField(max_digits=15, decimal_places=2, default=0.00)

    # Late Registration
    child_name = models.CharField(max_length=200, blank=True)
    child_birth_date = models.DateField(null=True, blank=True)
    child_birth_place = models.CharField(max_length=200, blank=True)
    father_name = models.CharField(max_length=200, blank=True)
    mother_name = models.CharField(max_length=200, blank=True)

    # Admin processing
    notes = models.TextField(blank=True, help_text='Admin notes (shown to resident on rejection)')
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='processed_cert_requests',
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Request #{self.pk} – {self.get_cert_type_display()} ({self.get_status_display()})"

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Certificate Request'
        verbose_name_plural = 'Certificate Requests'
