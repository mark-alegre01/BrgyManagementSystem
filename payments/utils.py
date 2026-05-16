from decimal import Decimal
from django.utils import timezone
from .models import Payment, OfficialReceipt

def calculate_certificate_fee(resident, cert_type):
    """
    Calculates the fee for a certificate request based on the resident's status.
    Auto-detects if the resident qualifies for a waiver.
    """
    # Fee Waivers for vulnerable sectors
    if (resident.is_indigent or 
        resident.is_pwd or 
        resident.is_senior_citizen or 
        resident.is_4ps_member or 
        resident.is_solo_parent):
        return Decimal('0.00'), True  # (Amount, IsWaived)

    # Standard Rates (matching certifications/views.py)
    rates = {
        'clearance': Decimal('100.00'),
        'residency': Decimal('50.00'),
        'indigency': Decimal('0.00'),
        'good_moral': Decimal('50.00'),
        'business_permit': Decimal('500.00'),
        'comelec': Decimal('50.00'),
        'cedula': Decimal('0.00'),  # Cedula has dynamic sizing usually, but for requests we can start at 0
        'late_registration': Decimal('50.00'),
    }
    
    fee = rates.get(cert_type, Decimal('50.00'))
    # Only auto-waive if fee is 0 AND it's not a Cedula (which has a dynamic price)
    is_waived = (fee == Decimal('0.00') and cert_type != 'cedula')
    return fee, is_waived

def generate_receipt_pdf(payment):
    """
    Generates a PDF official receipt using ReportLab.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, five_by_seven
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from io import BytesIO
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=five_by_seven, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        alignment=1, # Center
        fontSize=14,
        spaceAfter=10
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        alignment=1, # Center
        fontSize=10,
        spaceAfter=5
    )

    elements = []
    
    # 1. Letterhead
    elements.append(Paragraph("REPUBLIC OF THE PHILIPPINES", header_style))
    elements.append(Paragraph("PROVINCE OF SURIGAO DEL NORTE", header_style))
    elements.append(Paragraph("MUNICIPALITY OF GIGAQUIT", header_style))
    elements.append(Paragraph("<strong>BARANGAY SICO-SICO</strong>", title_style))
    elements.append(Spacer(1, 12))
    
    # 2. Receipt Title
    elements.append(Paragraph("OFFICIAL RECEIPT", title_style))
    elements.append(Spacer(1, 12))
    
    receipt = payment.official_receipt
    
    # 3. Receipt Details
    data = [
        ["OR Number:", receipt.or_number],
        ["Date:", receipt.created_at.strftime("%B %d, %Y %I:%M %p")],
        ["Payer Name:", receipt.resident_name],
        ["Particulars:", receipt.particulars],
        ["Amount Paid:", f"PHP {receipt.amount:,.2f}"],
        ["Payment Method:", payment.get_method_display()],
        ["Issued By:", f"{receipt.issued_by.first_name} {receipt.issued_by.last_name}"],
    ]
    
    table = Table(data, colWidths=[100, 150])
    table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(table)
    
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("--- This serves as your official proof of payment ---", header_style))
    
    doc.build(elements)
    
    buffer.seek(0)
    return buffer
