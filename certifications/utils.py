import io
from datetime import date
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from django.conf import settings


def generate_certificate_pdf(certificate):
    """Generate a styled PDF for any certificate type."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            topMargin=0.5 * inch, bottomMargin=0.5 * inch,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CertTitle', fontSize=18, alignment=TA_CENTER,
                               spaceAfter=6, fontName='Helvetica-Bold', textColor=colors.HexColor('#1a237e')))
    styles.add(ParagraphStyle(name='CertSubtitle', fontSize=11, alignment=TA_CENTER,
                               spaceAfter=4, fontName='Helvetica'))
    styles.add(ParagraphStyle(name='CertHeader', fontSize=14, alignment=TA_CENTER,
                               spaceAfter=20, fontName='Helvetica-Bold', textColor=colors.HexColor('#1565c0')))
    styles.add(ParagraphStyle(name='CertBody', fontSize=12, alignment=TA_JUSTIFY,
                               spaceAfter=12, fontName='Helvetica', leading=18))
    styles.add(ParagraphStyle(name='CertCenter', fontSize=12, alignment=TA_CENTER,
                               spaceAfter=8, fontName='Helvetica'))
    styles.add(ParagraphStyle(name='CertBold', fontSize=12, alignment=TA_CENTER,
                               fontName='Helvetica-Bold', spaceAfter=8))

    elements = []

    # Header
    brgy_name = getattr(settings, 'BARANGAY_NAME', 'Barangay Sample')
    municipality = getattr(settings, 'BARANGAY_MUNICIPALITY', 'Municipality of Sample')
    province = getattr(settings, 'BARANGAY_PROVINCE', 'Province of Sample')

    elements.append(Paragraph('Republic of the Philippines', styles['CertSubtitle']))
    elements.append(Paragraph(province, styles['CertSubtitle']))
    elements.append(Paragraph(municipality, styles['CertSubtitle']))
    elements.append(Paragraph(f'BARANGAY {brgy_name.upper()}', styles['CertTitle']))
    elements.append(Paragraph('Office of the Punong Barangay', styles['CertSubtitle']))
    elements.append(Spacer(1, 20))

    # Certificate type title
    cert_titles = {
        'clearance': 'BARANGAY CLEARANCE',
        'residency': 'CERTIFICATE OF RESIDENCY',
        'indigency': 'CERTIFICATE OF INDIGENCY',
        'good_moral': 'CERTIFICATE OF GOOD MORAL CHARACTER',
        'business_permit': 'BARANGAY BUSINESS CLEARANCE',
        'comelec': 'COMELEC CERTIFICATE',
        'cedula': 'COMMUNITY TAX CERTIFICATE',
        'late_registration': 'CERTIFICATE OF LATE REGISTRATION',
    }
    elements.append(Paragraph(cert_titles.get(certificate.cert_type, 'CERTIFICATE'), styles['CertHeader']))
    elements.append(Spacer(1, 10))

    resident = certificate.resident
    today_str = certificate.date_issued.strftime('%B %d, %Y') if certificate.date_issued else date.today().strftime('%B %d, %Y')

    # Body text based on certificate type
    if certificate.cert_type == 'clearance':
        body = f"""TO WHOM IT MAY CONCERN:
        <br/><br/>
        This is to certify that <b>{resident.full_name}</b>, of legal age, {resident.get_civil_status_display()},
        Filipino, and a resident of {resident.address}, {brgy_name}, {municipality}, {province},
        is known to be of good moral character and has no derogatory record filed in this barangay.
        <br/><br/>
        This certification is issued upon the request of the above-named person for <b>{certificate.purpose}</b>.
        <br/><br/>
        Issued this <b>{today_str}</b> at {brgy_name}, {municipality}, {province}.
        """
    elif certificate.cert_type == 'residency':
        body = f"""TO WHOM IT MAY CONCERN:
        <br/><br/>
        This is to certify that <b>{resident.full_name}</b>, {resident.age} years old,
        {resident.get_civil_status_display()}, Filipino, is a bonafide resident of
        {resident.address}, {brgy_name}, {municipality}, {province}.
        <br/><br/>
        This certification is issued upon the request of the above-named person for <b>{certificate.purpose}</b>.
        <br/><br/>
        Issued this <b>{today_str}</b> at {brgy_name}, {municipality}, {province}.
        """
    elif certificate.cert_type == 'indigency':
        body = f"""TO WHOM IT MAY CONCERN:
        <br/><br/>
        This is to certify that <b>{resident.full_name}</b>, {resident.age} years old,
        {resident.get_civil_status_display()}, Filipino, a resident of {resident.address},
        {brgy_name}, {municipality}, {province}, belongs to an indigent family
        in this barangay.
        <br/><br/>
        This certification is issued upon the request of the above-named person for <b>{certificate.purpose}</b>.
        <br/><br/>
        Issued this <b>{today_str}</b> at {brgy_name}, {municipality}, {province}.
        """
    elif certificate.cert_type == 'good_moral':
        body = f"""TO WHOM IT MAY CONCERN:
        <br/><br/>
        This is to certify that <b>{resident.full_name}</b>, {resident.age} years old,
        {resident.get_civil_status_display()}, Filipino, a resident of {resident.address},
        {brgy_name}, {municipality}, {province}, is known to me to be a person of
        good moral character and has no derogatory or criminal record in this barangay.
        <br/><br/>
        This certification is issued upon the request of the above-named person for <b>{certificate.purpose}</b>.
        <br/><br/>
        Issued this <b>{today_str}</b> at {brgy_name}, {municipality}, {province}.
        """
    elif certificate.cert_type == 'business_permit':
        body = f"""TO WHOM IT MAY CONCERN:
        <br/><br/>
        This is to certify that <b>{certificate.business_name}</b> owned/managed by
        <b>{resident.full_name}</b>, located at {certificate.business_address or resident.address},
        {brgy_name}, {municipality}, {province},
        is hereby granted clearance to operate within the jurisdiction of this barangay.
        <br/><br/>
        Type of Business: <b>{certificate.business_type}</b>
        <br/><br/>
        This certification is issued for <b>{certificate.purpose}</b>.
        <br/><br/>
        Issued this <b>{today_str}</b> at {brgy_name}, {municipality}, {province}.
        """
    else:
        body = f"""TO WHOM IT MAY CONCERN:
        <br/><br/>
        This is to certify that <b>{resident.full_name}</b>, {resident.age} years old,
        {resident.get_civil_status_display()}, Filipino, a resident of {resident.address},
        {brgy_name}, {municipality}, {province}.
        <br/><br/>
        This certification is issued for <b>{certificate.purpose}</b>.
        <br/><br/>
        Issued this <b>{today_str}</b> at {brgy_name}, {municipality}, {province}.
        """

    elements.append(Paragraph(body, styles['CertBody']))
    elements.append(Spacer(1, 40))

    # Signature block
    captain_name = getattr(settings, 'BARANGAY_CAPTAIN', 'HON. PUNONG BARANGAY')
    elements.append(Spacer(1, 30))
    sig_data = [
        ['', ''],
        ['', f'______________________________'],
        ['', f'{captain_name}'],
        ['', 'Punong Barangay'],
    ]
    sig_table = Table(sig_data, colWidths=[3.5 * inch, 3 * inch])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('FONTNAME', (1, 2), (1, 2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
    ]))
    elements.append(sig_table)

    # Footer with control number
    elements.append(Spacer(1, 30))
    elements.append(Paragraph(f'Control No.: <b>{certificate.control_number}</b>', styles['Normal']))
    if certificate.or_number:
        elements.append(Paragraph(f'OR No.: {certificate.or_number} | Amount: ₱{certificate.amount_paid}', styles['Normal']))

    doc.build(elements)
    buffer.seek(0)
    return buffer
