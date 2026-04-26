from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


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
    or_number = models.CharField(max_length=50, blank=True, null=True, unique=True, verbose_name='OR Number')
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
    
    @property
    def total_additional_tax(self):
        # Even more defensive conversion
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
        # Force basic tax and interest to Decimal
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
        # Set default basic tax if not provided
        if self.basic_tax == 0:
            self.basic_tax = Decimal('5.00') if self.taxpayer_type == 'individual' else Decimal('500.00')
            
        # Synchronize certificate amount_paid with total_amount
        self.certificate.amount_paid = self.total_amount
        self.certificate.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Cedula ({self.get_taxpayer_type_display()}) {self.ctc_number} - {self.certificate.resident}"

    class Meta:
        verbose_name = 'Cedula'
        verbose_name_plural = 'Cedulas'
