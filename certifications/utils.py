import io
import os
from datetime import date
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Frame, PageTemplate
from reportlab.lib import colors
from django.conf import settings
from django.contrib.staticfiles import finders


def draw_watermark(canvas, doc, is_resident=False):
    """Draw a faded logo as a watermark in the center of the page."""
    canvas.saveState()
    # Path to the barangay logo
    logo_path = os.path.join(settings.BASE_DIR, 'static/images/sico_sico_logo.jpg')
    if not os.path.exists(logo_path):
        # Fallback if specific name doesn't exist
        logo_path = os.path.join(settings.BASE_DIR, 'static/images/logo.png')
    
    if os.path.exists(logo_path):
        canvas.setFillAlpha(0.1)  # Set opacity to 10%
        # Calculate center
        img_width = 5 * inch
        img_height = 5 * inch
        x = (letter[0] - img_width) / 2
        y = (letter[1] - img_height) / 2
        canvas.drawImage(logo_path, x, y, width=img_width, height=img_height, mask='auto')
    
    # Add text watermark if resident
    if is_resident:
        canvas.setFillAlpha(0.15)
        canvas.setFont('Helvetica-Bold', 60)
        canvas.setFillColor(colors.red)
        canvas.translate(letter[0]/2, letter[1]/2)
        canvas.rotate(45)
        canvas.drawCentredString(0, 0, "NOT VALID WITHOUT SEAL")
        
    canvas.restoreState()


def generate_certificate_pdf(certificate, is_resident=False):
    """Generate a styled PDF for any certificate type."""
    if certificate.cert_type == 'cedula':
        return generate_cedula_pdf(certificate)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            topMargin=0.3 * inch, bottomMargin=0.3 * inch,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch)

    styles = getSampleStyleSheet()
    
    # Custom Styles
    styles.add(ParagraphStyle(name='CertHeaderLabel', fontSize=10, alignment=TA_CENTER,
                               fontName='Helvetica', leading=12))
    styles.add(ParagraphStyle(name='CertHeaderBrgy', fontSize=12, alignment=TA_CENTER,
                               fontName='Helvetica-Bold', leading=14))
    styles.add(ParagraphStyle(name='CertOffice', fontSize=16, alignment=TA_CENTER,
                               spaceBefore=20, spaceAfter=10, fontName='Times-Bold'))
    styles.add(ParagraphStyle(name='CertTitleLarge', fontSize=24, alignment=TA_CENTER,
                               spaceAfter=25, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CertToWhom', fontSize=14, alignment=TA_LEFT,
                               spaceAfter=15, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CertBody', fontSize=12, alignment=TA_JUSTIFY,
                               spaceAfter=12, fontName='Helvetica', leading=18))
    styles.add(ParagraphStyle(name='CertSignName', fontSize=14, alignment=TA_CENTER,
                               fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CertSignPos', fontSize=11, alignment=TA_CENTER,
                               fontName='Helvetica'))
    styles.add(ParagraphStyle(name='CertWarning', fontSize=10, alignment=TA_CENTER,
                               textColor=colors.red, fontName='Helvetica-BoldOblique'))

    elements = []

    # Paths to logos
    sico_logo_path = os.path.join(settings.BASE_DIR, 'static/images/sico_sico_logo.jpg')
    bagong_pilipinas_path = os.path.join(settings.BASE_DIR, 'static/images/bagong_pilipinas.png')
    gigaquit_logo_path = os.path.join(settings.BASE_DIR, 'static/images/gigaquit_logo.png')

    # Standardized logo size
    logo_w = 0.85 * inch
    logo_h = 0.85 * inch

    # Header Components
    img_sico = Image(sico_logo_path, width=logo_w, height=logo_h, kind='proportional') if os.path.exists(sico_logo_path) else Spacer(logo_w, logo_h)
    img_bagong = Image(bagong_pilipinas_path, width=logo_w, height=logo_h, kind='proportional') if os.path.exists(bagong_pilipinas_path) else Spacer(logo_w, logo_h)
    img_gigaquit = Image(gigaquit_logo_path, width=logo_w, height=logo_h, kind='proportional') if os.path.exists(gigaquit_logo_path) else Spacer(logo_w, logo_h)

    brgy_name = getattr(settings, 'BARANGAY_NAME', 'Sico-Sico')
    municipality = getattr(settings, 'BARANGAY_MUNICIPALITY', 'Gigaquit')
    province = getattr(settings, 'BARANGAY_PROVINCE', 'Surigao del Norte')
    
    # Fix redundant "Barangay" in title
    header_brgy_title = brgy_name.upper() if "BARANGAY" in brgy_name.upper() else f"BARANGAY {brgy_name.upper()}"
    
    center_text = [
        Paragraph('REPUBLIC OF THE PHILIPPINES', styles['CertHeaderLabel']),
        Paragraph(f'Province of {province}', styles['CertHeaderLabel']),
        Paragraph(f'Municipality of {municipality}', styles['CertHeaderLabel']),
        Paragraph(header_brgy_title, styles['CertHeaderBrgy']),
    ]
    
    # Create 5-column table to balance the logos and keep text perfectly centered
    # [Logo Sico] [Logo Bagong] [Center Text] [Logo Gigaquit] [Empty Balance]
    col_widths = [1.0*inch, 1.0*inch, 3.5*inch, 1.0*inch, 1.0*inch]
    header_table_data = [[img_sico, img_bagong, center_text, img_gigaquit, '']]
    
    header_table = Table(header_table_data, colWidths=col_widths)
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (1,0), 'CENTER'),
        ('ALIGN', (2,0), (2,0), 'CENTER'),
        ('ALIGN', (3,0), (3,0), 'CENTER'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    
    # Certificate Type Title Mapping
    cert_titles_map = {
        'clearance': 'BARANGAY CLEARANCE',
        'residency': 'CERTIFICATE OF RESIDENCY',
        'indigency': 'CERTIFICATE OF INDIGENCY',
        'good_moral': 'CERTIFICATE OF GOOD MORAL CHARACTER',
        'business_permit': 'BARANGAY BUSINESS CLEARANCE',
        'comelec': 'COMELEC CERTIFICATE',
        'cedula': 'COMMUNITY TAX CERTIFICATE',
        'late_registration': 'CERTIFICATE OF LATE REGISTRATION',
    }
    cert_display_title = cert_titles_map.get(certificate.cert_type, 'CERTIFICATE')

    elements.append(header_table)
    elements.append(Paragraph('OFFICE OF THE SANGGUNIANG BARANGAY', styles['CertOffice']))
    elements.append(Paragraph(cert_display_title, styles['CertTitleLarge']))

    resident = certificate.resident
    day = date.today().day
    month = date.today().strftime('%B')
    year = date.today().year
    
    # Body text based on certificate type
    if certificate.cert_type == 'clearance':
        body_text = f"This Clearance is hereby granted to <b>{resident.full_name.upper()}</b>, with residence at Barangay {brgy_name}, {municipality}, Surigao del Norte, in connection with this application for <b>{certificate.purpose}</b>."
        conclusion_text = f"It is understood that the issuance of this clearance shall not exempt the applicant/s from other requirements prescribed under the existing barangay ordinance of Barangay {brgy_name}, {municipality}, Surigao del Norte."
    elif certificate.cert_type == 'residency':
        body_text = f"This is to certify that <b>{resident.full_name.upper()}</b>, {resident.age} years old, {resident.get_civil_status_display()}, Filipino, is a bonafide resident of Barangay {brgy_name}, {municipality}, {province}."
        conclusion_text = f"This certification is issued upon the request of the above-named person for <b>{certificate.purpose}</b>."
    elif certificate.cert_type == 'indigency':
        body_text = f"This is to certify that <b>{resident.full_name.upper()}</b>, {resident.age} years old, {resident.get_civil_status_display()}, Filipino, a resident of Barangay {brgy_name}, {municipality}, {province}, belongs to an indigent family in this barangay."
        conclusion_text = f"This certification is issued upon the request of the above-named person for <b>{certificate.purpose}</b>."
    elif certificate.cert_type == 'good_moral':
        body_text = f"This is to certify that <b>{resident.full_name.upper()}</b>, {resident.age} years old, {resident.get_civil_status_display()}, Filipino, a resident of Barangay {brgy_name}, {municipality}, {province}, is known to me to be a person of good moral character and has no derogatory or criminal record in this barangay."
        conclusion_text = f"This certification is issued upon the request of the above-named person for <b>{certificate.purpose}</b>."
    elif certificate.cert_type == 'business_permit':
        body_text = f"This is to certify that <b>{certificate.business_name.upper()}</b> owned/managed by <b>{resident.full_name.upper()}</b>, located at {certificate.business_address or resident.address}, Barangay {brgy_name}, {municipality}, {province}, is hereby granted clearance to operate within the jurisdiction of this barangay.<br/><br/>Type of Business: <b>{certificate.business_type}</b>"
        conclusion_text = f"This certification is issued for <b>{certificate.purpose}</b>."
    else:
        body_text = f"This is to certify that <b>{resident.full_name.upper()}</b>, {resident.age} years old, {resident.get_civil_status_display()}, Filipino, a resident of Barangay {brgy_name}, {municipality}, {province}."
        conclusion_text = f"This certification is issued for <b>{certificate.purpose}</b>."

    issued_date_text = f"Given this <b>{day}th</b> day of <b>{month}, {year}</b>, at the Office of Punong Barangay of Barangay {brgy_name}, {municipality}, Surigao del Norte."

    elements.append(Paragraph('TO WHOM IT MAY CONCERN;', styles['CertToWhom']))
    elements.append(Paragraph(body_text, styles['CertBody']))
    elements.append(Paragraph(conclusion_text, styles['CertBody']))
    elements.append(Paragraph(f'Certification is issued upon the request of the above named for whatever legal purpose it may serve him/her best.', styles['CertBody']))
    elements.append(Spacer(1, 15))
    elements.append(Paragraph(issued_date_text, styles['CertBody']))
    elements.append(Spacer(1, 40))
    
    # Captain Signature - Optimized for full width to prevent clipping
    from officials.models import Official
    captain = Official.objects.filter(position='captain', status='active').first()
    captain_name = f"HON. {captain.resident.full_name.upper()}" if captain else getattr(settings, 'BARANGAY_CAPTAIN', 'NO ACTIVE CAPTAIN')
    sig_content = [
        Paragraph(captain_name, styles['CertSignName']),
        Paragraph('Punong Barangay', styles['CertSignPos'])
    ]
    sig_table = Table([['', sig_content]], colWidths=[3.5*inch, 4*inch])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
    ]))
    elements.append(sig_table)
    
    # Final warning
    elements.append(Spacer(1, 20))
    elements.append(Paragraph('“NOT VALID WITHOUT SEAL”', styles['CertWarning']))

    # Build PDF
    from functools import partial
    watermark_func = partial(draw_watermark, is_resident=is_resident)
    doc.build(elements, onFirstPage=watermark_func, onLaterPages=watermark_func)
    buffer.seek(0)
    return buffer


def generate_cedula_pdf(certificate, is_resident=False):
    """Generate an authentic-looking Cedula (Community Tax Certificate)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CedulaHeader', fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CedulaSubHeader', fontSize=10, alignment=TA_CENTER, fontName='Helvetica'))
    styles.add(ParagraphStyle(name='CedulaLabel', fontSize=8, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CedulaValue', fontSize=10, fontName='Helvetica'))
    styles.add(ParagraphStyle(name='CedulaMoney', fontSize=10, fontName='Helvetica', alignment=TA_RIGHT))
    
    elements = []
    
    cedula = certificate.cedula_details
    resident = certificate.resident
    is_corp = cedula.taxpayer_type == 'corporation'
    
    # Header
    header_title = 'COMMUNITY TAX CERTIFICATE'
    if is_corp:
        header_title += ' - CORPORATION'
    elements.append(Paragraph(header_title, styles['CedulaHeader']))
    elements.append(Paragraph(cedula.get_taxpayer_type_display().upper(), styles['CedulaSubHeader']))
    elements.append(Spacer(1, 10))
    
    # Place and Date of Issue
    header_data = [
        [Paragraph('YEAR', styles['CedulaLabel']), Paragraph('PLACE OF ISSUE (City / Municipality / Province)', styles['CedulaLabel']), Paragraph('DATE ISSUED', styles['CedulaLabel'])],
        [Paragraph(str(date.today().year), styles['CedulaValue']), Paragraph(cedula.place_of_issue, styles['CedulaValue']), Paragraph(date.today().strftime('%m/%d/%Y'), styles['CedulaValue'])]
    ]
    header_table = Table(header_data, colWidths=[1*inch, 4.5*inch, 1.5*inch])
    header_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(header_table)
    
    # CTC Number
    ctc_data = [[Paragraph('CTC NUMBER', styles['CedulaLabel']), Paragraph(cedula.ctc_number, styles['CedulaValue'])]]
    ctc_table = Table(ctc_data, colWidths=[1.5*inch, 5.5*inch])
    ctc_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
    ]))
    elements.append(ctc_table)
    
    # Name/Company
    name_label = 'NAME (Surname, First Name, Middle Name)' if not is_corp else 'COMPANY NAME'
    name_data = [
        [Paragraph(name_label, styles['CedulaLabel']), Paragraph('TIN (If any)', styles['CedulaLabel'])],
        [Paragraph(resident.full_name.upper(), styles['CedulaValue']), Paragraph('', styles['CedulaValue'])]
    ]
    name_table = Table(name_data, colWidths=[5.5*inch, 1.5*inch])
    name_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
    ]))
    elements.append(name_table)
    
    addr_data = [[Paragraph('ADDRESS', styles['CedulaLabel']), Paragraph(resident.address, styles['CedulaValue'])]]
    addr_table = Table(addr_data, colWidths=[1*inch, 6*inch])
    addr_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
    ]))
    elements.append(addr_table)
    
    if not is_corp:
        info_row1 = [
            [Paragraph('CITIZENSHIP', styles['CedulaLabel']), Paragraph('CIVIL STATUS', styles['CedulaLabel']), Paragraph('GENDER', styles['CedulaLabel']), Paragraph('BIRTH DATE', styles['CedulaLabel'])],
            [Paragraph(resident.nationality, styles['CedulaValue']), Paragraph(resident.get_civil_status_display(), styles['CedulaValue']), Paragraph(resident.get_gender_display(), styles['CedulaValue']), Paragraph(resident.birthdate.strftime('%m/%d/%Y'), styles['CedulaValue'])]
        ]
        info_table1 = Table(info_row1, colWidths=[1.75*inch, 1.75*inch, 1.75*inch, 1.75*inch])
        info_table1.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        elements.append(info_table1)
        
        info_row2 = [
            [Paragraph('PLACE OF BIRTH', styles['CedulaLabel']), Paragraph('HEIGHT', styles['CedulaLabel']), Paragraph('WEIGHT', styles['CedulaLabel']), Paragraph('PROFESSION / OCCUPATION', styles['CedulaLabel'])],
            [Paragraph(resident.birthplace, styles['CedulaValue']), Paragraph(cedula.height, styles['CedulaValue']), Paragraph(cedula.weight, styles['CedulaValue']), Paragraph(resident.occupation, styles['CedulaValue'])]
        ]
        info_table2 = Table(info_row2, colWidths=[1.75*inch, 1.1*inch, 1.1*inch, 3.05*inch])
        info_table2.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        elements.append(info_table2)
    else:
        corp_info = [[Paragraph('DATE OF INCORPORATION / REGISTRATION', styles['CedulaLabel']), Paragraph('NATURE OF BUSINESS', styles['CedulaLabel'])]]
        corp_table = Table(corp_info, colWidths=[3.5*inch, 3.5*inch])
        corp_table.setStyle(TableStyle([
            ('BOX', (0,0), (-1,-1), 1, colors.black),
            ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ]))
        elements.append(corp_table)
    
    elements.append(Spacer(1, 10))
    
    # Financial Section
    basic_label = 'BASIC COMMUNITY TAX (₱5.00) Voluntary or Exempted (₱1.00)' if not is_corp else 'BASIC COMMUNITY TAX (₱500.00)'
    fin_header = [[Paragraph('COMMUNITY TAX DUE', styles['CedulaLabel']), Paragraph(basic_label, styles['CedulaLabel']), Paragraph('AMOUNT', styles['CedulaLabel'])]]
    fin_table_h = Table(fin_header, colWidths=[3.5*inch, 2.5*inch, 1.5*inch])
    fin_table_h.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
    ]))
    elements.append(fin_table_h)
    
    # Calculate capped additional tax for display
    raw_additional = cedula.total_additional_tax
    addl_cap = Decimal('5000.00') if not is_corp else Decimal('10000.00')
    capped_additional = min(raw_additional, addl_cap)
    
    if not is_corp:
        fin_data = [
            [Paragraph('1. BASIC COMMUNITY TAX', styles['CedulaValue']), '', Paragraph(f"{cedula.basic_tax:,.2f}", styles['CedulaMoney'])],
            [Paragraph('2. ADDITIONAL COMMUNITY TAX (Taxable amount not to exceed ₱5,000.00)', styles['CedulaValue']), '', ''],
            [Paragraph('   (a) GROSS ANNUAL SALARY OR EARNINGS DERIVED FROM EXERCISE OF PROFESSION (₱1.00 for every ₱1,000)', styles['CedulaValue']), '', Paragraph(f"{cedula.additional_tax_income:,.2f}", styles['CedulaMoney'])],
            [Paragraph('   (b) GROSS RECEIPTS OR EARNINGS DERIVED FROM BUSINESS DURING THE PRECEDING YEAR (₱1.00 for every ₱1,000)', styles['CedulaValue']), '', Paragraph(f"{cedula.additional_tax_business:,.2f}", styles['CedulaMoney'])],
            [Paragraph('   (c) INCOME FROM REAL PROPERTY (₱1.00 for every ₱1,000)', styles['CedulaValue']), '', Paragraph(f"{cedula.additional_tax_property:,.2f}", styles['CedulaMoney'])],
        ]
    else:
        fin_data = [
            [Paragraph('1. BASIC COMMUNITY TAX', styles['CedulaValue']), '', Paragraph(f"{cedula.basic_tax:,.2f}", styles['CedulaMoney'])],
            [Paragraph('2. ADDITIONAL COMMUNITY TAX (Taxable amount not to exceed ₱10,000.00)', styles['CedulaValue']), '', ''],
            [Paragraph('   (a) ASSESSED VALUE OF REAL PROPERTY OWNED (₱2.00 for every ₱5,000)', styles['CedulaValue']), '', Paragraph(f"{cedula.additional_tax_property:,.2f}", styles['CedulaMoney'])],
            [Paragraph('   (b) GROSS RECEIPTS OR EARNINGS FROM BUSINESS (₱2.00 for every ₱5,000)', styles['CedulaValue']), '', Paragraph(f"{cedula.additional_tax_business:,.2f}", styles['CedulaMoney'])],
        ]
        
    fin_data.extend([
        [Paragraph('TOTAL (Basic + Capped Additional)', styles['CedulaValue']), '', Paragraph(f"{(cedula.basic_tax + capped_additional):,.2f}", styles['CedulaMoney'])],
        [Paragraph('INTEREST', styles['CedulaValue']), '', Paragraph(f"{cedula.interest:,.2f}", styles['CedulaMoney'])],
        [Paragraph('TOTAL AMOUNT PAID', styles['CedulaHeader']), '', Paragraph(f"₱{cedula.total_amount:,.2f}", styles['CedulaHeader'])],
    ])
    
    fin_table = Table(fin_data, colWidths=[3.5*inch, 2.5*inch, 1.5*inch])
    fin_table.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black),
        ('ALIGN', (2,0), (2,-1), 'RIGHT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(fin_table)
    
    elements.append(Spacer(1, 40))
    
    # Signatures
    label1 = "Taxpayer's Signature" if not is_corp else "Authorized Representative"
    label2 = "Municipal/City Treasurer"
    
    sig_data = [
        [Paragraph('_______________________________', styles['CedulaValue']), Paragraph('_______________________________', styles['CedulaValue'])],
        [Paragraph(label1, styles['CedulaSubHeader']), Paragraph(label2, styles['CedulaSubHeader'])]
    ]
    sig_table = Table(sig_data, colWidths=[3.5*inch, 3.5*inch])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    elements.append(sig_table)
    
    from functools import partial
    watermark_func = partial(draw_watermark, is_resident=is_resident)
    doc.build(elements, onFirstPage=watermark_func)
    buffer.seek(0)
    return buffer


def generate_receipt_pdf(certificate):
    """
    Generate a 2-copy printable receipt (Resident & Barangay copies) on a single A4/Letter page.
    """
    buffer = io.BytesIO()
    # Using letter size which is 8.5 x 11 inches
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch)
    
    styles = getSampleStyleSheet()
    
    # Custom styles for receipt
    styles.add(ParagraphStyle(name='ReceiptHeader', fontSize=10, alignment=TA_CENTER, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CertHeaderLabel', fontSize=10, alignment=TA_CENTER, fontName='Helvetica', leading=12))
    styles.add(ParagraphStyle(name='ReceiptTitle', fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold', spaceBefore=10, spaceAfter=10))
    styles.add(ParagraphStyle(name='ReceiptLabel', fontSize=11, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='ReceiptValue', fontSize=11, fontName='Helvetica'))
    styles.add(ParagraphStyle(name='CopyLabel', fontSize=9, alignment=TA_RIGHT, fontName='Helvetica-Oblique', textColor=colors.grey))

    def create_receipt_elements(copy_type):
        elements = []
        
        # Copy indicator
        elements.append(Paragraph(f"{copy_type} COPY", styles['CopyLabel']))
        
        # Header
        brgy_name = getattr(settings, 'BARANGAY_NAME', 'Sico-Sico')
        municipality = getattr(settings, 'BARANGAY_MUNICIPALITY', 'Gigaquit')
        province = getattr(settings, 'BARANGAY_PROVINCE', 'Surigao del Norte')
        
        elements.append(Paragraph('REPUBLIC OF THE PHILIPPINES', styles['ReceiptHeader']))
        elements.append(Paragraph(f'Barangay {brgy_name.upper()}, {municipality}, {province}', styles['ReceiptHeader']))
        elements.append(Paragraph('OFFICIAL RECEIPT', styles['ReceiptTitle']))
        
        # Receipt Data Table
        data = [
            [Paragraph('Control Number:', styles['ReceiptLabel']), Paragraph(certificate.control_number, styles['ReceiptValue'])],
            [Paragraph('OR Number:', styles['ReceiptLabel']), Paragraph(certificate.or_number or "N/A", styles['ReceiptValue'])],
            [Paragraph('Date Issued:', styles['ReceiptLabel']), Paragraph(certificate.created_at.strftime('%B %d, %Y'), styles['ReceiptValue'])],
            [Paragraph('Received From:', styles['ReceiptLabel']), Paragraph(certificate.resident.full_name, styles['ReceiptValue'])],
            [Paragraph('Nature of Payment:', styles['ReceiptLabel']), Paragraph(certificate.get_cert_type_display(), styles['ReceiptValue'])],
            [Paragraph('Purpose:', styles['ReceiptLabel']), Paragraph(certificate.purpose, styles['ReceiptValue'])],
            [Paragraph('Amount Paid:', styles['ReceiptLabel']), Paragraph(f"<b>PHP {certificate.amount_paid:,.2f}</b>", styles['ReceiptValue'])],
        ]
        
        t = Table(data, colWidths=[1.8 * inch, 5.2 * inch])
        t.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 0.4 * inch))
        
        # Signature block
        sig_data = [
            [Paragraph('__________________________', styles['ReceiptHeader']), Spacer(1, 1), Paragraph('__________________________', styles['ReceiptHeader'])],
            [Paragraph('Resident Signature', styles['CertHeaderLabel']), Spacer(1, 1), Paragraph('Barangay Collector/Treasurer', styles['CertHeaderLabel'])]
        ]
        sig_table = Table(sig_data, colWidths=[3 * inch, 1 * inch, 3 * inch])
        elements.append(sig_table)
        
        return elements

    # Combine Resident and Barangay copies
    all_elements = []
    
    # Resident Copy
    all_elements.extend(create_receipt_elements("RESIDENT"))
    
    # Separation Dash Line
    all_elements.append(Spacer(1, 0.5 * inch))
    all_elements.append(Paragraph('-' * 140, styles['ReceiptHeader']))
    all_elements.append(Spacer(1, 0.5 * inch))
    
    # Barangay Copy
    all_elements.extend(create_receipt_elements("BARANGAY"))
    
    doc.build(all_elements)
    buffer.seek(0)
    return buffer
