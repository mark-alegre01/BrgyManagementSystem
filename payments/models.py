from django.db import models
from django.conf import settings
from datetime import date

class OfficialReceipt(models.Model):
    """Stores information about the issued Official Receipt (OR)."""
    or_number = models.CharField(max_length=50, unique=True, verbose_name="OR Number")
    resident_name = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    particulars = models.TextField(help_text="Description of what is being paid for (e.g. Barangay Clearance)")
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="issued_receipts")
    issued_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.or_number} - {self.resident_name}"

    @staticmethod
    def generate_next_or_number():
        """Generates the next OR number in the format OR-YYYY-XXXXX."""
        year = date.today().year
        last_receipt = OfficialReceipt.objects.filter(or_number__startswith=f"OR-{year}-").order_by('-or_number').first()
        
        if last_receipt:
            # Extract the last 5 digits and increment
            last_number = int(last_receipt.or_number.split('-')[-1])
            new_number = last_number + 1
        else:
            new_number = 1
            
        return f"OR-{year}-{new_number:05d}"

    class Meta:
        verbose_name = "Official Receipt"
        verbose_name_plural = "Official Receipts"
        ordering = ["-issued_at"]

class Payment(models.Model):
    """Handles the payment transaction details."""
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash at Hall'),
        ('gcash', 'GCash'),
        ('waived', 'Waived'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('unpaid', 'Unpaid'),
        ('pending', 'Pending Verification'),
        ('paid', 'Paid'),
        ('waived', 'Waived'),
    ]
    
    method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # GCash details
    proof_screenshot = models.ImageField(upload_to='payments/proofs/', blank=True, null=True)
    gcash_ref_number = models.CharField(max_length=100, blank=True, null=True, verbose_name="GCash Reference Number")
    
    # Link to OR if paid via Cash/GCash
    official_receipt = models.OneToOneField(OfficialReceipt, on_delete=models.SET_NULL, null=True, blank=True, related_name="payment_record")
    
    # Waiver details
    waive_reason = models.TextField(blank=True, null=True)
    
    # Audit details
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_payments")
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment {self.id} ({self.get_status_display()})"

    class Meta:
        verbose_name = "Payment"
        verbose_name_plural = "Payments"
        ordering = ["-created_at"]
