from decimal import Decimal
from django.utils import timezone
from .models import Payment, OfficialReceipt

def calculate_certificate_fee(resident, cert_type, cert_request=None):
    """
    Calculates the fee for a certificate request based on the resident's status.
    Auto-detects if the resident qualifies for a waiver.
    """
    # Fee Waiver for First Time Jobseekers (RA 11261) is now handled strictly upon admin approval 
    # of the RA11261Application, which will manually set the payment to 0 and issue an EXEMPT receipt.

    # Standard Rates (matching certifications/views.py)
    rates = {
        'clearance': Decimal('100.00'),
        'residency': Decimal('50.00'),
        'indigency': Decimal('0.00'),
        'good_moral': Decimal('50.00'),
        'business_permit': Decimal('500.00'),
        'comelec': Decimal('50.00'),
        'cedula': Decimal('0.00'),  # Base rate
        'late_registration': Decimal('50.00'),
    }
    
    fee = rates.get(cert_type, Decimal('50.00'))
    
    if cert_type == 'cedula' and cert_request:
        is_indiv = cert_request.taxpayer_type == 'individual'
        basic = Decimal('5.00') if is_indiv else Decimal('500.00')
        cap = Decimal('5000.00') if is_indiv else Decimal('10000.00')
        
        def to_d(val):
            if val is None: return Decimal('0.00')
            try: return Decimal(str(val))
            except: return Decimal('0.00')

        raw_prop = to_d(cert_request.raw_taxable_property)
        raw_bus = to_d(cert_request.raw_taxable_business)
        raw_inc = to_d(cert_request.raw_taxable_income)
        
        vProp = Decimal('0.00')
        vBus = Decimal('0.00')
        vInc = Decimal('0.00')
        
        if is_indiv:
            if raw_prop: vProp = (raw_prop / Decimal('1000')).quantize(Decimal('0.01'))
            if raw_bus: vBus = (raw_bus / Decimal('1000')).quantize(Decimal('0.01'))
            if raw_inc: vInc = (raw_inc / Decimal('1000')).quantize(Decimal('0.01'))
        else:
            if raw_prop: vProp = ((raw_prop / Decimal('5000')) * Decimal('2')).quantize(Decimal('0.01'))
            if raw_bus: vBus = ((raw_bus / Decimal('5000')) * Decimal('2')).quantize(Decimal('0.01'))
                
        additional = vProp + vBus + vInc
        if additional > cap:
            additional = cap
            
        fee = basic + additional

    # Only auto-waive if fee is 0 AND it's not a Cedula
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
