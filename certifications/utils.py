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

def draw_watermark(canvas, doc, is_resident=False):
    """Draw a faded logo as a watermark in the center of the page."""
    canvas.saveState()
    logo_path = os.path.join(settings.BASE_DIR, 'static/images/sico_sico_logo.jpg')
    if not os.path.exists(logo_path):
        logo_path = os.path.join(settings.BASE_DIR, 'static/images/logo.png')
    
    if os.path.exists(logo_path):
        canvas.setFillAlpha(0.1)
        img_width = 5 * inch
        img_height = 5 * inch
        x = (letter[0] - img_width) / 2
        y = (letter[1] - img_height) / 2
        canvas.drawImage(logo_path, x, y, width=img_width, height=img_height, mask='auto')
    
    if is_resident:
        canvas.setFillAlpha(0.15)
        canvas.setFont('Helvetica-Bold', 60)
        canvas.setFillColor(colors.red)
        canvas.translate(letter[0]/2, letter[1]/2)
        canvas.rotate(45)
        
    canvas.restoreState()

def generate_certificate_pdf(certificate, is_resident=False):
    """Generate a styled PDF for any certificate type."""
    if certificate.cert_type == 'cedula':
        return generate_cedula_pdf(certificate)
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch)

    styles = getSampleStyleSheet()
    
    # Custom Styles (Using Times-Roman for formal certs)
    styles.add(ParagraphStyle(name='CertHeaderLabel', fontSize=11, alignment=TA_CENTER,
                               fontName='Times-Roman', leading=14))
    styles.add(ParagraphStyle(name='CertOffice', fontSize=14, alignment=TA_CENTER,
                               spaceBefore=25, spaceAfter=20, fontName='Times-Bold'))
    styles.add(ParagraphStyle(name='CertTitleLarge', fontSize=20, alignment=TA_CENTER,
                               spaceAfter=25, fontName='Times-Bold', leading=24))
    styles.add(ParagraphStyle(name='CertToWhom', fontSize=12, alignment=TA_LEFT,
                               spaceAfter=15, fontName='Times-Bold'))
    styles.add(ParagraphStyle(name='CertBody', fontSize=12, alignment=TA_JUSTIFY,
                               spaceAfter=12, fontName='Times-Roman', leading=18, firstLineIndent=36))
    styles.add(ParagraphStyle(name='CertBodyNoIndent', fontSize=12, alignment=TA_JUSTIFY,
                               spaceAfter=12, fontName='Times-Roman', leading=18))
    styles.add(ParagraphStyle(name='CertSignName', fontSize=14, alignment=TA_CENTER,
                               fontName='Times-Bold'))
    styles.add(ParagraphStyle(name='CertSignPos', fontSize=12, alignment=TA_CENTER,
                               fontName='Times-Roman'))
    styles.add(ParagraphStyle(name='CertWarning', fontSize=10, alignment=TA_CENTER,
                               fontName='Times-Italic'))

    elements = []

    sico_logo_path = os.path.join(settings.BASE_DIR, 'static/images/logo.png')
    bagong_pilipinas_path = os.path.join(settings.BASE_DIR, 'static/images/bagong_pilipinas.png')
    gigaquit_logo_path = os.path.join(settings.BASE_DIR, 'static/images/gigaquit_logo.png')

    logo_w = 1.0 * inch
    logo_h = 1.0 * inch

    img_sico = Image(sico_logo_path, width=logo_w, height=logo_h, kind='bound') if os.path.exists(sico_logo_path) else Spacer(logo_w, logo_h)
    img_bagong = Image(bagong_pilipinas_path, width=0.9*inch, height=0.7*inch, kind='bound') if os.path.exists(bagong_pilipinas_path) else Spacer(0.9*inch, 0.7*inch)
    img_gigaquit = Image(gigaquit_logo_path, width=logo_w, height=logo_h, kind='bound') if os.path.exists(gigaquit_logo_path) else Spacer(logo_w, logo_h)
    
    center_text = [
        Paragraph('Republic of the Philippines', styles['CertHeaderLabel']),
        Paragraph('Province of Surigao Del Norte', styles['CertHeaderLabel']),
        Paragraph('Municipality of Gigaquit', styles['CertHeaderLabel']),
        Paragraph('Barangay Sico-Sico', styles['CertHeaderLabel']),
    ]
    
    col_widths = [1.1*inch, 1.0*inch, 3.8*inch, 1.1*inch]
    header_table_data = [[img_sico, img_bagong, center_text, img_gigaquit]]
    
    header_table = Table(header_table_data, colWidths=col_widths)
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    
    cert_titles_map = {
        'clearance': 'BARANGAY CLEARANCE',
        'residency': 'CERTIFICATE OF RESIDENCY',
        'indigency': 'CERTIFICATE OF INDIGENCY',
        'good_moral': 'BARANGAY CERTIFICATION',
        'business_permit': 'BARANGAY BUSINESS CLEARANCE',
        'comelec': 'COMELEC CERTIFICATE',
        'cedula': 'COMMUNITY TAX CERTIFICATE',
        'late_registration': 'CERTIFICATE OF LATE REGISTRATION',
    }
    cert_display_title = cert_titles_map.get(certificate.cert_type, 'BARANGAY CERTIFICATION')

    elements.append(header_table)
    elements.append(Paragraph('OFFICE OF THE SANGGUNIANG BARANGAY', styles['CertOffice']))
    elements.append(Paragraph(f"<u>{cert_display_title}</u>", styles['CertTitleLarge']))
    elements.append(Paragraph('TO WHOM IT MAY CONCERN:', styles['CertToWhom']))

    resident = certificate.resident
    day = date.today().day
    month = date.today().strftime('%B')
    year = date.today().year
    
    def get_ordinal(n):
        if 11 <= (n % 100) <= 13: return f"{n}th"
        return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"

    day_str = get_ordinal(day)
    address = resident.address or "Purok 3 Barangay Sico-Sico, Gigaquit, Surigao del Norte"
    
    # Body text based on certificate type
    if certificate.cert_type == 'clearance':
        elements.append(Paragraph("This Certification is hereby granted to:", styles['CertBodyNoIndent']))
        table_data = [
            [Paragraph('Full Name', styles['CertBodyNoIndent']), Paragraph(f": <b>{resident.full_name.title()}</b>", styles['CertBodyNoIndent'])],
            [Paragraph('Address', styles['CertBodyNoIndent']), Paragraph(f": {address}", styles['CertBodyNoIndent'])],
            [Paragraph('Birthday', styles['CertBodyNoIndent']), Paragraph(f": {resident.birthdate.strftime('%B %d, %Y')}", styles['CertBodyNoIndent'])],
            [Paragraph('Place of birth', styles['CertBodyNoIndent']), Paragraph(f": {resident.birthplace or 'Gigaquit, Surigao del Norte'}", styles['CertBodyNoIndent'])],
            [Paragraph('Civil Status', styles['CertBodyNoIndent']), Paragraph(f": {resident.get_civil_status_display().title()}", styles['CertBodyNoIndent'])],
            [Paragraph('Gender', styles['CertBodyNoIndent']), Paragraph(f": {resident.get_gender_display().title()}", styles['CertBodyNoIndent'])],
            [Paragraph('Age', styles['CertBodyNoIndent']), Paragraph(f": {resident.age or '--'}", styles['CertBodyNoIndent'])],
        ]
        info_table = Table(table_data, colWidths=[1.5*inch, 4.0*inch])
        info_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'TOP'), ('BOTTOMPADDING', (0,0), (-1,-1), 0), ('TOPPADDING', (0,0), (-1,-1), 0)]))
        elements.append(info_table)
        elements.append(Spacer(1, 15))
        elements.append(Paragraph("The above name person is known to be of Good Moral Character and integrity , a law abiding citizen in the community no derogatory records, no pending case filed in this office as of this date as far as records is concern.", styles['CertBody']))
        elements.append(Paragraph("This certification is being issued upon the request of the above-named person for whatever legal purpose it may serve his/her best.", styles['CertBody']))
        elements.append(Paragraph(f"Done this <b>{day_str}</b> day of <b>{month} {year}</b> at the office of Punong Barangay of Barangay Sico- sico, Gigaquit, Surigao del Norte.", styles['CertBody']))

    elif certificate.cert_type == 'indigency':
        elements.append(Paragraph(f"This is to certify that <b>{resident.full_name.upper()}</b>, of legal age, {resident.get_civil_status_display().lower()}, Filipino citizen, and a resident of {address}.", styles['CertBody']))
        elements.append(Paragraph("Further certifies, that the said person is one among the list of INDIGENT in this barangay per records kept in this office.", styles['CertBody']))
        elements.append(Paragraph("This certification is being issued upon the request of the above-named person for whatever legal purpose it may serve.", styles['CertBody']))
        elements.append(Paragraph(f"Given & issued this <b>{day_str}</b> day of <b>{month} {year}</b>, at Barangay Sico-Sico, Gigaquit, Surigao del Norte, Philippines.", styles['CertBody']))

    elif certificate.cert_type == 'residency':
        elements.append(Paragraph(f"This is to certify that <b>{resident.full_name.upper()}</b>, of legal age, {resident.get_civil_status_display().lower()}, Filipino citizen, and a resident of {address}.", styles['CertBody']))
        elements.append(Paragraph("Further certifies, that the person named above is a resident of this barangay, living with his/her family up to the present, and is a member of our community.", styles['CertBody']))
        purpose = certificate.purpose or "bank account opening purposes"
        elements.append(Paragraph(f"This certification is being issued upon the request of the above-named person for <b>{purpose}</b>.", styles['CertBody']))
        elements.append(Paragraph(f"Given & issued this <b>{day_str}</b> day of <b>{month} {year}</b>, at Barangay Sico-Sico, Gigaquit, Surigao del Norte, Philippines.", styles['CertBody']))

    elif certificate.cert_type == 'business_permit':
        elements.append(Paragraph("Pursuant to existing ordinance of this barangay, CLEARANCE is granted to", styles['CertBody']))
        
        # Center Applicant
        elements.append(Paragraph(f"<b><u>{resident.full_name.upper()}</u></b>", styles['CertSignName']))
        elements.append(Paragraph("Name of Applicant", styles['CertSignPos']))
        elements.append(Spacer(1, 15))
        
        # Center Business Name
        b_name = certificate.business_name.upper() if certificate.business_name else "--"
        elements.append(Paragraph(f"<b><u>{b_name}</u></b>", styles['CertSignName']))
        elements.append(Paragraph("Business Name", styles['CertSignPos']))
        elements.append(Spacer(1, 15))
        
        # Center Address
        b_addr = certificate.business_address if certificate.business_address else "Ladgaron, Claver, Surigao del Norte"
        elements.append(Paragraph(f"<b><u>{b_addr}</u></b>", ParagraphStyle(name='temp1', fontSize=12, alignment=TA_CENTER, fontName='Times-Bold')))
        elements.append(Paragraph("Business Address", styles['CertSignPos']))
        elements.append(Spacer(1, 15))
        
        elements.append(Paragraph("Applicant is hereby advised to follow strictly existing ordinance in relation with the conduct of his/her business. Violation of the same is a ground for the revocation of this clearance.", styles['CertBody']))
        elements.append(Paragraph(f"Clearance is valid up to {certificate.date_issued.strftime('%B %d')}, {certificate.date_issued.year + 1} unless revoked due to a valid reason.", styles['CertBody']))
        elements.append(Paragraph(f"WITNESS MY HAND AND SEAL this <b>{day_str}</b> day of <b>{month} {year}</b>, at Barangay Sico-Sico, Gigaquit, Surigao del Norte, Philippines.", styles['CertBody']))

    else:
        # General / Good Moral
        elements.append(Paragraph(f"This is to certify that <b>{resident.full_name.upper()}</b>, of legal age, {resident.get_gender_display().lower()}, Filipino citizen, is a bonafide resident at {address}. A law abiding citizen, possesses a GOOD MORAL CHARACTER and has no derogatory records filed in this office.", styles['CertBody']))
        elements.append(Paragraph(f"Further certifies, that the said person was born on {resident.birthdate.strftime('%B %d, %Y')} at {resident.birthplace or '--'}.", styles['CertBody']))
        elements.append(Paragraph("This certification is being issued upon the request of the above-named person for whatever legal purpose it may serve.", styles['CertBody']))
        elements.append(Paragraph(f"Issued this <b>{day_str}</b> day of <b>{month} {year}</b>, at Barangay Sico-Sico, Gigaquit, Surigao del Norte, Philippines.", styles['CertBody']))

    elements.append(Spacer(1, 40))
    
    from officials.models import Official
    captain = Official.objects.filter(position='captain', status='active').first()
    captain_name = f"HON. {captain.resident.full_name.upper()}" if captain else getattr(settings, 'BARANGAY_CAPTAIN', 'HON. MARITES R. MANONGAS')
    
    # Bottom Layout (Clearance Details + Signature)
    if certificate.cert_type == 'clearance':
        left_block = [
            Paragraph(f"OR No. {certificate.or_number or '__________'}", styles['CertBodyNoIndent']),
            Paragraph(f"Issued on: {certificate.date_issued.strftime('%B %d, %Y')}", styles['CertBodyNoIndent']),
            Paragraph("Issued at: Sico-Sico, Gigaquit, SDN", styles['CertBodyNoIndent'])
        ]
    else:
        left_block = []
        
    sig_content = [
        Paragraph(captain_name, styles['CertSignName']),
        Paragraph('Punong Barangay', styles['CertSignPos']),
        Spacer(1, 10),
        Paragraph('Not valid without official seal', styles['CertWarning'])
    ]
    
    sig_table = Table([[left_block, sig_content]], colWidths=[3.5*inch, 3.5*inch])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('ALIGN', (1,0), (1,0), 'CENTER'),
        ('ALIGN', (0,0), (0,0), 'LEFT'),
    ]))
    elements.append(sig_table)
    
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
    
    header_title = 'COMMUNITY TAX CERTIFICATE'
    if is_corp:
        header_title += ' - CORPORATION'
    elements.append(Paragraph(header_title, styles['CedulaHeader']))
    elements.append(Paragraph(cedula.get_taxpayer_type_display().upper(), styles['CedulaSubHeader']))
    elements.append(Spacer(1, 10))
    
    header_data = [
        [Paragraph('YEAR', styles['CedulaLabel']), Paragraph('PLACE OF ISSUE (City / Municipality / Province)', styles['CedulaLabel']), Paragraph('DATE ISSUED', styles['CedulaLabel'])],
        [Paragraph(str(date.today().year), styles['CedulaValue']), Paragraph(cedula.place_of_issue, styles['CedulaValue']), Paragraph(date.today().strftime('%m/%d/%Y'), styles['CedulaValue'])]
    ]
    header_table = Table(header_data, colWidths=[1*inch, 4.5*inch, 1.5*inch])
    header_table.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, colors.black), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black), ('VALIGN', (0,0), (-1,-1), 'TOP')]))
    elements.append(header_table)
    
    ctc_data = [[Paragraph('CTC NUMBER', styles['CedulaLabel']), Paragraph(cedula.ctc_number, styles['CedulaValue'])]]
    ctc_table = Table(ctc_data, colWidths=[1.5*inch, 5.5*inch])
    ctc_table.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, colors.black), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black)]))
    elements.append(ctc_table)
    
    name_label = 'NAME (Surname, First Name, Middle Name)' if not is_corp else 'COMPANY NAME'
    name_data = [
        [Paragraph(name_label, styles['CedulaLabel']), Paragraph('TIN (If any)', styles['CedulaLabel'])],
        [Paragraph(resident.full_name.upper(), styles['CedulaValue']), Paragraph('', styles['CedulaValue'])]
    ]
    name_table = Table(name_data, colWidths=[5.5*inch, 1.5*inch])
    name_table.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, colors.black), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black)]))
    elements.append(name_table)
    
    addr_data = [[Paragraph('ADDRESS', styles['CedulaLabel']), Paragraph(resident.address, styles['CedulaValue'])]]
    addr_table = Table(addr_data, colWidths=[1*inch, 6*inch])
    addr_table.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, colors.black), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black)]))
    elements.append(addr_table)
    
    if not is_corp:
        info_row1 = [
            [Paragraph('CITIZENSHIP', styles['CedulaLabel']), Paragraph('CIVIL STATUS', styles['CedulaLabel']), Paragraph('GENDER', styles['CedulaLabel']), Paragraph('BIRTH DATE', styles['CedulaLabel'])],
            [Paragraph(resident.nationality, styles['CedulaValue']), Paragraph(resident.get_civil_status_display(), styles['CedulaValue']), Paragraph(resident.get_gender_display(), styles['CedulaValue']), Paragraph(resident.birthdate.strftime('%m/%d/%Y'), styles['CedulaValue'])]
        ]
        info_table1 = Table(info_row1, colWidths=[1.75*inch, 1.75*inch, 1.75*inch, 1.75*inch])
        info_table1.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, colors.black), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black)]))
        elements.append(info_table1)
        
        info_row2 = [
            [Paragraph('PLACE OF BIRTH', styles['CedulaLabel']), Paragraph('HEIGHT', styles['CedulaLabel']), Paragraph('WEIGHT', styles['CedulaLabel']), Paragraph('PROFESSION / OCCUPATION', styles['CedulaLabel'])],
            [Paragraph(resident.birthplace, styles['CedulaValue']), Paragraph(cedula.height, styles['CedulaValue']), Paragraph(cedula.weight, styles['CedulaValue']), Paragraph(resident.occupation, styles['CedulaValue'])]
        ]
        info_table2 = Table(info_row2, colWidths=[1.75*inch, 1.1*inch, 1.1*inch, 3.05*inch])
        info_table2.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, colors.black), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black)]))
        elements.append(info_table2)
    else:
        corp_info = [[Paragraph('DATE OF INCORPORATION / REGISTRATION', styles['CedulaLabel']), Paragraph('NATURE OF BUSINESS', styles['CedulaLabel'])]]
        corp_table = Table(corp_info, colWidths=[3.5*inch, 3.5*inch])
        corp_table.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, colors.black), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black)]))
        elements.append(corp_table)
    
    elements.append(Spacer(1, 10))
    
    basic_label = 'BASIC COMMUNITY TAX (₱5.00) Voluntary or Exempted (₱1.00)' if not is_corp else 'BASIC COMMUNITY TAX (₱500.00)'
    fin_header = [[Paragraph('COMMUNITY TAX DUE', styles['CedulaLabel']), Paragraph(basic_label, styles['CedulaLabel']), Paragraph('AMOUNT', styles['CedulaLabel'])]]
    fin_table_h = Table(fin_header, colWidths=[3.5*inch, 2.5*inch, 1.5*inch])
    fin_table_h.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, colors.black), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black), ('BACKGROUND', (0,0), (-1,0), colors.lightgrey)]))
    elements.append(fin_table_h)
    
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
    fin_table.setStyle(TableStyle([('BOX', (0,0), (-1,-1), 1, colors.black), ('INNERGRID', (0,0), (-1,-1), 0.5, colors.black), ('ALIGN', (2,0), (2,-1), 'RIGHT'), ('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    elements.append(fin_table)
    
    elements.append(Spacer(1, 40))
    
    label1 = "Taxpayer's Signature" if not is_corp else "Authorized Representative"
    label2 = "Municipal/City Treasurer"
    
    sig_data = [
        [Paragraph('_______________________________', styles['CedulaValue']), Paragraph('_______________________________', styles['CedulaValue'])],
        [Paragraph(label1, styles['CedulaSubHeader']), Paragraph(label2, styles['CedulaSubHeader'])]
    ]
    sig_table = Table(sig_data, colWidths=[3.5*inch, 3.5*inch])
    sig_table.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    elements.append(sig_table)
    
    from functools import partial
    watermark_func = partial(draw_watermark, is_resident=is_resident)
    doc.build(elements, onFirstPage=watermark_func)
    buffer.seek(0)
    return buffer

def generate_receipt_pdf(certificate):
    """Generate a 2-copy printable receipt."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5 * inch, bottomMargin=0.5 * inch, leftMargin=0.5 * inch, rightMargin=0.5 * inch)
    
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReceiptHeader', fontSize=10, alignment=TA_CENTER, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CertHeaderLabel', fontSize=10, alignment=TA_CENTER, fontName='Helvetica', leading=12))
    styles.add(ParagraphStyle(name='ReceiptTitle', fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold', spaceBefore=10, spaceAfter=10))
    styles.add(ParagraphStyle(name='ReceiptLabel', fontSize=11, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='ReceiptValue', fontSize=11, fontName='Helvetica'))
    styles.add(ParagraphStyle(name='CopyLabel', fontSize=9, alignment=TA_RIGHT, fontName='Helvetica-Oblique', textColor=colors.grey))

    def create_receipt_elements(copy_type):
        elements = []
        elements.append(Paragraph(f"{copy_type} COPY", styles['CopyLabel']))
        brgy_name = getattr(settings, 'BARANGAY_NAME', 'Sico-Sico')
        municipality = getattr(settings, 'BARANGAY_MUNICIPALITY', 'Gigaquit')
        province = getattr(settings, 'BARANGAY_PROVINCE', 'Surigao del Norte')
        
        # Receipt logos header
        r_sico_path = os.path.join(settings.BASE_DIR, 'static/images/logo.png')
        r_bagong_path = os.path.join(settings.BASE_DIR, 'static/images/bagong_pilipinas.png')
        r_gigaquit_path = os.path.join(settings.BASE_DIR, 'static/images/gigaquit_logo.png')
        r_sico = Image(r_sico_path, width=0.6*inch, height=0.6*inch, kind='bound') if os.path.exists(r_sico_path) else Spacer(0.6*inch, 0.6*inch)
        r_bagong = Image(r_bagong_path, width=0.55*inch, height=0.45*inch, kind='bound') if os.path.exists(r_bagong_path) else Spacer(0.55*inch, 0.45*inch)
        r_gigaquit = Image(r_gigaquit_path, width=0.6*inch, height=0.6*inch, kind='bound') if os.path.exists(r_gigaquit_path) else Spacer(0.6*inch, 0.6*inch)
        receipt_center_text = [
            Paragraph('REPUBLIC OF THE PHILIPPINES', styles['ReceiptHeader']),
            Paragraph(f'Province of Surigao del Norte', styles['CertHeaderLabel']),
            Paragraph(f'Municipality of Gigaquit', styles['CertHeaderLabel']),
            Paragraph(f'Barangay {brgy_name.upper()}', styles['ReceiptHeader']),
        ]
        logo_row = Table([[r_sico, r_bagong, receipt_center_text, r_gigaquit]], colWidths=[0.8*inch, 0.75*inch, 4.9*inch, 0.8*inch])
        logo_row.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE'), ('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        elements.append(logo_row)
        elements.append(Paragraph('OFFICIAL RECEIPT', styles['ReceiptTitle']))
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
        t.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 0.5, colors.grey), ('PADDING', (0, 0), (-1, -1), 6), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE')]))
        elements.append(t)
        elements.append(Spacer(1, 0.4 * inch))
        sig_data = [
            [Paragraph('__________________________', styles['ReceiptHeader']), Spacer(1, 1), Paragraph('__________________________', styles['ReceiptHeader'])],
            [Paragraph('Resident Signature', styles['CertHeaderLabel']), Spacer(1, 1), Paragraph('Barangay Collector/Treasurer', styles['CertHeaderLabel'])]
        ]
        sig_table = Table(sig_data, colWidths=[3 * inch, 1 * inch, 3 * inch])
        elements.append(sig_table)
        return elements

    all_elements = []
    all_elements.extend(create_receipt_elements("RESIDENT"))
    all_elements.append(Spacer(1, 0.5 * inch))
    all_elements.append(Paragraph('-' * 140, styles['ReceiptHeader']))
    all_elements.append(Spacer(1, 0.5 * inch))
    all_elements.append(Spacer(1, 0.5 * inch))
    all_elements.extend(create_receipt_elements("BARANGAY"))
    
    doc.build(all_elements)
    buffer.seek(0)
    return buffer
