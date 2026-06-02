from django.db import models


class Ordinance(models.Model):
    """Barangay ordinance/resolution record."""
    CATEGORY_CHOICES = [
        ('peace_order', 'Peace and Order'),
        ('health', 'Health and Sanitation'),
        ('environment', 'Environment'),
        ('revenue', 'Revenue and Finance'),
        ('infrastructure', 'Infrastructure'),
        ('social_welfare', 'Social Welfare'),
        ('education', 'Education'),
        ('other', 'Other'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('amended', 'Amended'),
        ('repealed', 'Repealed'),
        ('pending', 'Pending'),
    ]

    ordinance_number = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)
    author = models.CharField(max_length=200)
    date_enacted = models.DateField()
    date_effectivity = models.DateField(null=True, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='other')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # File attachment
    document_file = models.FileField(upload_to='ordinances/', blank=True, null=True)

    # Parsed Content
    body_content = models.TextField(blank=True, help_text="Full text of the ordinance")
    signatories = models.TextField(blank=True, help_text="Signatories of the ordinance")

    sponsor = models.CharField(max_length=200, blank=True)
    remarks = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Ordinance No. {self.ordinance_number}: {self.title}"

    class Meta:
        ordering = ['-date_enacted']
        verbose_name = 'Ordinance'
        verbose_name_plural = 'Ordinances'
