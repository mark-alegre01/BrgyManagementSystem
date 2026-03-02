import io
import os
from datetime import date
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Frame, PageTemplate
from reportlab.lib import colors
from django.conf import settings
from django.contrib.staticfiles import finders


def draw_watermark(canvas, doc):
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
    canvas.restoreState()


def generate_certificate_pdf(certificate):
    """Generate a styled PDF for any certificate type."""
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
    img_sico = Image(sico_logo_path, width=logo_w, height=logo_h) if os.path.exists(sico_logo_path) else Spacer(logo_w, logo_h)
    img_bagong = Image(bagong_pilipinas_path, width=logo_w, height=logo_h) if os.path.exists(bagong_pilipinas_path) else Spacer(logo_w, logo_h)
    img_gigaquit = Image(gigaquit_logo_path, width=logo_w, height=logo_h) if os.path.exists(gigaquit_logo_path) else Spacer(logo_w, logo_h)

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
    captain_name = getattr(settings, 'BARANGAY_CAPTAIN', 'HON. MARITES R. MANONGAS')
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
    doc.build(elements, onFirstPage=draw_watermark, onLaterPages=draw_watermark)
    buffer.seek(0)
    return buffer


