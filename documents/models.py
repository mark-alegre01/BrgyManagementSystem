from django.db import models
from django.conf import settings

class Document(models.Model):
    DOCUMENT_TYPES = [
        ('clearance', 'Barangay Clearance'),
        ('residency', 'Certificate of Residency'),
        ('indigency', 'Certificate of Indigency'),
        ('business', 'Business Permit'),
        ('ordinance', 'Ordinance'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES, default='other')
    content = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_documents')

    def __str__(self):
        return f"{self.title} ({self.get_document_type_display()})"
    
    class Meta:
        ordering = ['-updated_at']
