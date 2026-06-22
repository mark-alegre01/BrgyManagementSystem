import io
import os
from datetime import date
from decimal import Decimal
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Flowable
from reportlab.lib import colors
from django.conf import settings


# ─── Logo Paths ──────────────────────────────────────────────────────────────

def _logo(filename):
    return os.path.join(settings.BASE_DIR, f'static/images/{filename}')


SICO_LOGO    = _logo('sico_sico_logo.png')
BAGONG_LOGO  = _logo('bagong_pilipinas.png')
GIGAQUIT_LOGO = _logo('gigaquit_logo.png')
HEADER_FOOTER_IMG = _logo('header-footer.png')


def draw_page_template(canvas, doc, certificate=None, is_resident=False):
    """
    Draws on EVERY page:
      - Watermark (faded logo at center)
      - Header: header-footer.png + logos + text
      - Footer: header-footer.png (flipped) + 'Not valid without official seal'
    """
    canvas.saveState()
    page_w, page_h = letter
    margin = 0.5 * inch

    # ── Watermark ────────────────────────────────────────────────────────────
    if os.path.exists(SICO_LOGO):
        canvas.setFillAlpha(0.07)
        wm_size = 5.0 * inch
        canvas.drawImage(
            SICO_LOGO,
            (page_w - wm_size) / 2,
            (page_h - wm_size) / 2,
            width=wm_size, height=wm_size,
            mask='auto', preserveAspectRatio=True,
        )

    # ── Header Banner ────────────────────────────────────────────────────────
    canvas.setFillAlpha(1.0)
    header_h = 1.35 * inch
    header_y = page_h - header_h

    # Draw the header-footer image
    if os.path.exists(HEADER_FOOTER_IMG):
        canvas.drawImage(HEADER_FOOTER_IMG, 0, header_y, width=page_w, height=header_h, preserveAspectRatio=False)

    # Logos on top of banner
    logo_size = 0.80 * inch
    logo_y = header_y + (header_h - logo_size) / 2

    # Barangay logo (left 1)
    if os.path.exists(SICO_LOGO):
        canvas.drawImage(
            SICO_LOGO,
            margin + 0.15 * inch, logo_y,
            width=logo_size, height=logo_size,
            mask='auto', preserveAspectRatio=True,
        )

    # Bagong Pilipinas logo (left 2)
    if os.path.exists(BAGONG_LOGO):
        canvas.drawImage(
            BAGONG_LOGO,
            margin + 0.15 * inch + logo_size + 0.1 * inch, logo_y + 0.05 * inch,
            width=logo_size * 1.25, height=logo_size * 0.85,
            mask='auto', preserveAspectRatio=True,
        )

    # Gigaquit logo (right)
    if os.path.exists(GIGAQUIT_LOGO):
        canvas.drawImage(
            GIGAQUIT_LOGO,
            page_w - margin - logo_size - 0.15 * inch, logo_y,
            width=logo_size, height=logo_size,
            mask='auto', preserveAspectRatio=True,
        )

    # Center text on banner
    center_x = page_w / 2
    header_lines = [
        ('Republic of the Philippines', 'Times-Roman', 11),
        ('Province of Surigao Del Norte', 'Times-Roman', 11),
        ('Municipality of Gigaquit', 'Times-Roman', 11),
        ('Barangay Sico-Sico', 'Times-Bold', 13),
    ]
    line_spacing = 14
    text_start_y = header_y + header_h - 0.25 * inch
    for text, font, size in header_lines:
        canvas.setFont(font, size)
        canvas.setFillColor(colors.black)
        canvas.setFillAlpha(1.0)
        canvas.drawCentredString(center_x, text_start_y, text)
        text_start_y -= line_spacing

    # ── Footer Banner ────────────────────────────────────────────────────────
    footer_h = 0.65 * inch
    footer_y = 0

    # Draw the header-footer image (flipped vertically)
    if os.path.exists(HEADER_FOOTER_IMG):
        canvas.saveState()
        canvas.translate(0, footer_h)
        canvas.scale(1, -1)
        canvas.drawImage(HEADER_FOOTER_IMG, 0, 0, width=page_w, height=footer_h, preserveAspectRatio=False)
        canvas.restoreState()

    # "Not valid without official seal" in red italic
    canvas.setFillAlpha(1.0)
    canvas.setFont('Times-BoldItalic', 10)
    canvas.setFillColor(colors.red)
    canvas.drawCentredString(center_x, footer_h / 2 + 0.02 * inch, 'Not valid without official seal')

    # Control number & page on footer
    canvas.setFont('Times-Roman', 7)
    canvas.setFillColor(colors.black)
    if certificate:
        try:
            ctrl = certificate.control_number
        except Exception:
            ctrl = ''
        canvas.drawString(margin + 0.1 * inch, 0.12 * inch, f'Control No: {ctrl}')
    canvas.drawRightString(page_w - margin - 0.1 * inch, 0.12 * inch, f'Page {doc.page}')

    canvas.restoreState()


    canvas.restoreState()


class HeaderBannerFlowable(Flowable):
    """Custom flowable to draw the exact header banner inline for receipts."""
    def __init__(self):
        Flowable.__init__(self)
        self.width = letter[0]
        self.height = 1.35 * inch

    def draw(self):
        canvas = self.canv
        page_w = self.width
        margin = 0.5 * inch
        
        # Shift origin left by margin to cover full width
        canvas.saveState()
        canvas.translate(-margin, 0)
        
        if os.path.exists(HEADER_FOOTER_IMG):
            canvas.drawImage(HEADER_FOOTER_IMG, 0, 0, width=page_w, height=self.height, preserveAspectRatio=False)

        logo_size = 0.80 * inch
        logo_y = (self.height - logo_size) / 2

        if os.path.exists(SICO_LOGO):
            canvas.drawImage(SICO_LOGO, margin + 0.15 * inch, logo_y, width=logo_size, height=logo_size, mask='auto', preserveAspectRatio=True)

        if os.path.exists(BAGONG_LOGO):
            canvas.drawImage(BAGONG_LOGO, margin + 0.15 * inch + logo_size + 0.1 * inch, logo_y + 0.05 * inch, width=logo_size * 1.25, height=logo_size * 0.85, mask='auto', preserveAspectRatio=True)

        if os.path.exists(GIGAQUIT_LOGO):
            canvas.drawImage(GIGAQUIT_LOGO, page_w - margin - logo_size - 0.15 * inch, logo_y, width=logo_size, height=logo_size, mask='auto', preserveAspectRatio=True)

        center_x = page_w / 2
        header_lines = [
            ('Republic of the Philippines', 'Times-Roman', 11),
            ('Province of Surigao Del Norte', 'Times-Roman', 11),
            ('Municipality of Gigaquit', 'Times-Roman', 11),
            ('Barangay Sico-Sico', 'Times-Bold', 13),
        ]
        line_spacing = 14
        text_start_y = self.height - 0.25 * inch
        for text, font, size in header_lines:
            canvas.setFont(font, size)
            canvas.setFillColor(colors.black)
            canvas.setFillAlpha(1.0)
            canvas.drawCentredString(center_x, text_start_y, text)
            text_start_y -= line_spacing
            
        canvas.restoreState()

def draw_receipt_template(canvas, doc):
    """Draws only the watermarks for the receipt page. Headers are flowables."""
    canvas.saveState()
    page_w, page_h = letter
    
    if os.path.exists(SICO_LOGO):
        canvas.setFillAlpha(0.07)
        wm_size = 4.0 * inch
        canvas.drawImage(SICO_LOGO, (page_w - wm_size) / 2, page_h * 0.75 - wm_size / 2, width=wm_size, height=wm_size, mask='auto', preserveAspectRatio=True)
        canvas.drawImage(SICO_LOGO, (page_w - wm_size) / 2, page_h * 0.25 - wm_size / 2, width=wm_size, height=wm_size, mask='auto', preserveAspectRatio=True)
        
    canvas.restoreState()


# ─── Helper ──────────────────────────────────────────────────────────────────

def get_ordinal(n):
    if 11 <= (n % 100) <= 13:
        return f'{n}th'
    return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"


# ─── Certificate PDF ──────────────────────────────────────────────────────────

def generate_certificate_pdf(certificate, is_resident=False):
    """Generate a styled PDF for any certificate type."""
    if certificate.cert_type == 'cedula':
        return generate_cedula_pdf(certificate, is_resident=is_resident)

    buffer = io.BytesIO()
    # topMargin leaves room for canvas header; bottomMargin leaves room for footer
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=1.45 * inch, bottomMargin=0.90 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CertOffice', fontSize=14, alignment=TA_CENTER,
                               spaceBefore=6, spaceAfter=6, fontName='Times-Bold'))
    styles.add(ParagraphStyle(name='CertTitleLarge', fontSize=20, alignment=TA_CENTER,
                               spaceAfter=18, fontName='Times-Bold', leading=24))
    styles.add(ParagraphStyle(name='CertToWhom', fontSize=12, alignment=TA_LEFT,
                               spaceAfter=12, fontName='Times-Bold'))
    styles.add(ParagraphStyle(name='CertBody', fontSize=12, alignment=TA_JUSTIFY,
                               spaceAfter=12, fontName='Times-Roman', leading=18,
                               firstLineIndent=36))
    styles.add(ParagraphStyle(name='CertBodyNoIndent', fontSize=12, alignment=TA_JUSTIFY,
                               spaceAfter=8, fontName='Times-Roman', leading=18))
    styles.add(ParagraphStyle(name='CertSignName', fontSize=14, alignment=TA_CENTER,
                               fontName='Times-Bold'))
    styles.add(ParagraphStyle(name='CertSignPos', fontSize=12, alignment=TA_CENTER,
                               fontName='Times-Roman'))

    elements = []

    cert_titles_map = {
        'clearance':       'BARANGAY CLEARANCE',
        'residency':       'CERTIFICATE OF RESIDENCY',
        'indigency':       'CERTIFICATE OF INDIGENCY',
        'good_moral':      'BARANGAY CERTIFICATION',
        'business_permit': 'BARANGAY BUSINESS CLEARANCE',
        'comelec':         'COMELEC CERTIFICATE',
        'late_registration': 'CERTIFICATE OF LATE REGISTRATION',
    }
    cert_display_title = cert_titles_map.get(certificate.cert_type, 'BARANGAY CERTIFICATION')

    elements.append(Paragraph('OFFICE OF THE SANGGUNIANG BARANGAY', styles['CertOffice']))
    elements.append(Paragraph(f'<u>{cert_display_title}</u>', styles['CertTitleLarge']))
    elements.append(Paragraph('TO WHOM IT MAY CONCERN:', styles['CertToWhom']))

    resident = certificate.resident
    today = date.today()
    day_str = get_ordinal(today.day)
    month   = today.strftime('%B')
    year    = today.year
    address = resident.address or 'Purok 3 Barangay Sico-Sico, Gigaquit, Surigao del Norte'

    # ── Body text per cert type ───────────────────────────────────────────────
    if certificate.cert_type == 'clearance':
        elements.append(Paragraph('This Certification is hereby granted to:', styles['CertBodyNoIndent']))
        table_data = [
            [Paragraph('Full Name',      styles['CertBodyNoIndent']), Paragraph(f': <b>{resident.full_name.title()}</b>', styles['CertBodyNoIndent'])],
            [Paragraph('Address',        styles['CertBodyNoIndent']), Paragraph(f': {address}', styles['CertBodyNoIndent'])],
            [Paragraph('Birthday',       styles['CertBodyNoIndent']), Paragraph(f': {resident.birthdate.strftime("%B %d, %Y")}', styles['CertBodyNoIndent'])],
            [Paragraph('Place of birth', styles['CertBodyNoIndent']), Paragraph(f': {resident.birthplace or "Gigaquit, Surigao del Norte"}', styles['CertBodyNoIndent'])],
            [Paragraph('Civil Status',   styles['CertBodyNoIndent']), Paragraph(f': {resident.get_civil_status_display().title()}', styles['CertBodyNoIndent'])],
            [Paragraph('Gender',         styles['CertBodyNoIndent']), Paragraph(f': {resident.get_gender_display().title()}', styles['CertBodyNoIndent'])],
            [Paragraph('Age',            styles['CertBodyNoIndent']), Paragraph(f': {resident.age or "--"}', styles['CertBodyNoIndent'])],
        ]
        info_table = Table(table_data, colWidths=[1.5 * inch, 4.5 * inch])
        info_table.setStyle(TableStyle([
            ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 15))
        elements.append(Paragraph(
            'The above name person is known to be of Good Moral Character and integrity, '
            'a law abiding citizen in the community no derogatory records, no pending case '
            'filed in this office as of this date as far as records is concern.',
            styles['CertBody']))
        elements.append(Paragraph(
            'This certification is being issued upon the request of the above-named person '
            'for whatever legal purpose it may serve his/her best.',
            styles['CertBody']))
        elements.append(Paragraph(
            f'Done this <b>{day_str}</b> day of <b>{month} {year}</b> at the office of '
            'Punong Barangay of Barangay Sico-Sico, Gigaquit, Surigao del Norte.',
            styles['CertBody']))

    elif certificate.cert_type == 'indigency':
        elements.append(Paragraph(
            f'This is to certify that <b>{resident.full_name.upper()}</b>, of legal age, '
            f'{resident.get_civil_status_display().lower()}, Filipino citizen, and a resident of {address}.',
            styles['CertBody']))
        elements.append(Paragraph(
            'Further certifies, that the said person is one among the list of INDIGENT in '
            'this barangay per records kept in this office.',
            styles['CertBody']))
        elements.append(Paragraph(
            'This certification is being issued upon the request of the above-named person '
            'for whatever legal purpose it may serve.',
            styles['CertBody']))
        elements.append(Paragraph(
            f'Given &amp; issued this <b>{day_str}</b> day of <b>{month} {year}</b>, '
            'at Barangay Sico-Sico, Gigaquit, Surigao del Norte, Philippines.',
            styles['CertBody']))

    elif certificate.cert_type == 'residency':
        elements.append(Paragraph(
            f'This is to certify that <b>{resident.full_name.upper()}</b>, of legal age, '
            f'{resident.get_civil_status_display().lower()}, Filipino citizen, and a '
            f'resident of {address}.',
            styles['CertBody']))
        elements.append(Paragraph(
            'Further certifies, that the person named above is a resident of this barangay, '
            'living with his/her family up to the present, and is a member of our community.',
            styles['CertBody']))
        purpose = certificate.purpose or 'bank account opening purposes'
        elements.append(Paragraph(
            f'This certification is being issued upon the request of the above-named person '
            f'for <b>{purpose}</b>.',
            styles['CertBody']))
        elements.append(Paragraph(
            f'Given &amp; issued this <b>{day_str}</b> day of <b>{month} {year}</b>, '
            'at Barangay Sico-Sico, Gigaquit, Surigao del Norte, Philippines.',
            styles['CertBody']))

    elif certificate.cert_type == 'business_permit':
        elements.append(Paragraph(
            'Pursuant to existing ordinance of this barangay, CLEARANCE is granted to',
            styles['CertBody']))
        elements.append(Paragraph(f'<b><u>{resident.full_name.upper()}</u></b>', styles['CertSignName']))
        elements.append(Paragraph('Name of Applicant', styles['CertSignPos']))
        elements.append(Spacer(1, 12))
        b_name = certificate.business_name.upper() if certificate.business_name else '--'
        elements.append(Paragraph(f'<b><u>{b_name}</u></b>', styles['CertSignName']))
        elements.append(Paragraph('Business Name', styles['CertSignPos']))
        elements.append(Spacer(1, 12))
        b_addr = certificate.business_address or 'Barangay Sico-Sico, Gigaquit, Surigao del Norte'
        elements.append(Paragraph(
            f'<b><u>{b_addr}</u></b>',
            ParagraphStyle(name='BAddrStyle', fontSize=12, alignment=TA_CENTER, fontName='Times-Bold')))
        elements.append(Paragraph('Business Address', styles['CertSignPos']))
        elements.append(Spacer(1, 12))
        elements.append(Paragraph(
            'Applicant is hereby advised to follow strictly existing ordinance in relation '
            'with the conduct of his/her business. Violation of the same is a ground for '
            'the revocation of this clearance.',
            styles['CertBody']))
        elements.append(Paragraph(
            f'Clearance is valid up to {certificate.date_issued.strftime("%B %d")}, '
            f'{certificate.date_issued.year + 1} unless revoked due to a valid reason.',
            styles['CertBody']))
        elements.append(Paragraph(
            f'WITNESS MY HAND AND SEAL this <b>{day_str}</b> day of <b>{month} {year}</b>, '
            'at Barangay Sico-Sico, Gigaquit, Surigao del Norte, Philippines.',
            styles['CertBody']))

    else:
        # Good Moral / General
        elements.append(Paragraph(
            f'This is to certify that <b>{resident.full_name.upper()}</b>, of legal age, '
            f'{resident.get_gender_display().lower()}, Filipino citizen, is a bonafide '
            f'resident at {address}. A law abiding citizen, possesses a GOOD MORAL '
            'CHARACTER and has no derogatory records filed in this office.',
            styles['CertBody']))
        elements.append(Paragraph(
            f'Further certifies, that the said person was born on '
            f'{resident.birthdate.strftime("%B %d, %Y")} at {resident.birthplace or "--"}.',
            styles['CertBody']))
        elements.append(Paragraph(
            'This certification is being issued upon the request of the above-named person '
            'for whatever legal purpose it may serve.',
            styles['CertBody']))
        elements.append(Paragraph(
            f'Issued this <b>{day_str}</b> day of <b>{month} {year}</b>, '
            'at Barangay Sico-Sico, Gigaquit, Surigao del Norte, Philippines.',
            styles['CertBody']))

    elements.append(Spacer(1, 40))

    # ── Signature block ───────────────────────────────────────────────────────
    from officials.models import Official
    captain = Official.objects.filter(position='captain', status='active').first()
    captain_name = (
        f'HON. {captain.resident.full_name.upper()}' if captain
        else getattr(settings, 'BARANGAY_CAPTAIN', 'HON. PUNONG BARANGAY')
    )

    if certificate.cert_type == 'clearance':
        left_block = [
            Paragraph(f'OR No. {certificate.or_number or "__________"}', styles['CertBodyNoIndent']),
            Paragraph(f'Issued on: {certificate.date_issued.strftime("%B %d, %Y")}', styles['CertBodyNoIndent']),
            Paragraph('Issued at: Sico-Sico, Gigaquit, SDN', styles['CertBodyNoIndent']),
        ]
    else:
        left_block = []

    sig_content = [
        Paragraph(captain_name, styles['CertSignName']),
        Paragraph('Punong Barangay', styles['CertSignPos']),
    ]

    sig_table = Table([[left_block, sig_content]], colWidths=[3.5 * inch, 3.5 * inch])
    sig_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('ALIGN',  (1, 0), (1, 0),  'CENTER'),
        ('ALIGN',  (0, 0), (0, 0),  'LEFT'),
    ]))
    elements.append(sig_table)

    # ── Build ─────────────────────────────────────────────────────────────────
    from functools import partial
    page_func = partial(draw_page_template, certificate=certificate, is_resident=is_resident)
    doc.build(elements, onFirstPage=page_func, onLaterPages=page_func)
    buffer.seek(0)
    return buffer


# ─── Cedula PDF ───────────────────────────────────────────────────────────────

def generate_cedula_pdf(certificate, is_resident=False):
    """Generate an authentic-looking Cedula (Community Tax Certificate)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=1.45 * inch, bottomMargin=0.90 * inch,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='CedulaHeader',    fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CedulaSubHeader', fontSize=10, alignment=TA_CENTER, fontName='Helvetica'))
    styles.add(ParagraphStyle(name='CedulaLabel',     fontSize=8,  fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CedulaValue',     fontSize=10, fontName='Helvetica'))
    styles.add(ParagraphStyle(name='CedulaMoney',     fontSize=10, fontName='Helvetica', alignment=TA_RIGHT))

    elements = []
    cedula   = certificate.cedula_details
    resident = certificate.resident
    is_corp  = cedula.taxpayer_type == 'corporation'

    header_title = 'COMMUNITY TAX CERTIFICATE'
    if is_corp:
        header_title += ' - CORPORATION'
    elements.append(Paragraph(header_title, styles['CedulaHeader']))
    elements.append(Paragraph(cedula.get_taxpayer_type_display().upper(), styles['CedulaSubHeader']))
    elements.append(Spacer(1, 10))

    # Year / Place / Date
    header_data = [
        [Paragraph('YEAR', styles['CedulaLabel']),
         Paragraph('PLACE OF ISSUE (City / Municipality / Province)', styles['CedulaLabel']),
         Paragraph('DATE ISSUED', styles['CedulaLabel'])],
        [Paragraph(str(date.today().year), styles['CedulaValue']),
         Paragraph(cedula.place_of_issue, styles['CedulaValue']),
         Paragraph(date.today().strftime('%m/%d/%Y'), styles['CedulaValue'])],
    ]
    header_table = Table(header_data, colWidths=[1 * inch, 4.5 * inch, 1.5 * inch])
    header_table.setStyle(TableStyle([
        ('BOX',       (0, 0), (-1, -1), 1,   colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('VALIGN',    (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(header_table)

    # CTC Number
    ctc_data = [[Paragraph('CTC NUMBER', styles['CedulaLabel']),
                 Paragraph(cedula.ctc_number, styles['CedulaValue'])]]
    ctc_table = Table(ctc_data, colWidths=[1.5 * inch, 5.5 * inch])
    ctc_table.setStyle(TableStyle([
        ('BOX',       (0, 0), (-1, -1), 1,   colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(ctc_table)

    # Name
    name_label = 'NAME (Surname, First Name, Middle Name)' if not is_corp else 'COMPANY NAME'
    name_data = [
        [Paragraph(name_label, styles['CedulaLabel']),     Paragraph('TIN (If any)', styles['CedulaLabel'])],
        [Paragraph(resident.full_name.upper(), styles['CedulaValue']), Paragraph('', styles['CedulaValue'])],
    ]
    name_table = Table(name_data, colWidths=[5.5 * inch, 1.5 * inch])
    name_table.setStyle(TableStyle([
        ('BOX',       (0, 0), (-1, -1), 1,   colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(name_table)

    # Address
    addr_data = [[Paragraph('ADDRESS', styles['CedulaLabel']),
                  Paragraph(resident.address, styles['CedulaValue'])]]
    addr_table = Table(addr_data, colWidths=[1 * inch, 6 * inch])
    addr_table.setStyle(TableStyle([
        ('BOX',       (0, 0), (-1, -1), 1,   colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(addr_table)

    if not is_corp:
        info_row1 = [
            [Paragraph('CITIZENSHIP',  styles['CedulaLabel']),
             Paragraph('CIVIL STATUS', styles['CedulaLabel']),
             Paragraph('GENDER',       styles['CedulaLabel']),
             Paragraph('BIRTH DATE',   styles['CedulaLabel'])],
            [Paragraph(resident.nationality,                  styles['CedulaValue']),
             Paragraph(resident.get_civil_status_display(),   styles['CedulaValue']),
             Paragraph(resident.get_gender_display(),         styles['CedulaValue']),
             Paragraph(resident.birthdate.strftime('%m/%d/%Y'), styles['CedulaValue'])],
        ]
        info_table1 = Table(info_row1, colWidths=[1.75 * inch] * 4)
        info_table1.setStyle(TableStyle([
            ('BOX',       (0, 0), (-1, -1), 1,   colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(info_table1)

        info_row2 = [
            [Paragraph('PLACE OF BIRTH',          styles['CedulaLabel']),
             Paragraph('HEIGHT',                  styles['CedulaLabel']),
             Paragraph('WEIGHT',                  styles['CedulaLabel']),
             Paragraph('PROFESSION / OCCUPATION', styles['CedulaLabel'])],
            [Paragraph(resident.birthplace,     styles['CedulaValue']),
             Paragraph(cedula.height,           styles['CedulaValue']),
             Paragraph(cedula.weight,           styles['CedulaValue']),
             Paragraph(resident.occupation,     styles['CedulaValue'])],
        ]
        info_table2 = Table(info_row2, colWidths=[1.75 * inch, 1.1 * inch, 1.1 * inch, 3.05 * inch])
        info_table2.setStyle(TableStyle([
            ('BOX',       (0, 0), (-1, -1), 1,   colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(info_table2)
    else:
        corp_info = [[Paragraph('DATE OF INCORPORATION / REGISTRATION', styles['CedulaLabel']),
                      Paragraph('NATURE OF BUSINESS', styles['CedulaLabel'])]]
        corp_table = Table(corp_info, colWidths=[3.5 * inch, 3.5 * inch])
        corp_table.setStyle(TableStyle([
            ('BOX',       (0, 0), (-1, -1), 1,   colors.black),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
        ]))
        elements.append(corp_table)

    elements.append(Spacer(1, 10))

    # Financial section
    basic_label = ('BASIC COMMUNITY TAX (₱5.00) Voluntary or Exempted (₱1.00)'
                   if not is_corp else 'BASIC COMMUNITY TAX (₱500.00)')
    fin_header = [[Paragraph('COMMUNITY TAX DUE', styles['CedulaLabel']),
                   Paragraph(basic_label, styles['CedulaLabel']),
                   Paragraph('AMOUNT', styles['CedulaLabel'])]]
    fin_table_h = Table(fin_header, colWidths=[3.5 * inch, 2.5 * inch, 1.5 * inch])
    fin_table_h.setStyle(TableStyle([
        ('BOX',        (0, 0), (-1, -1), 1,   colors.black),
        ('INNERGRID',  (0, 0), (-1, -1), 0.5, colors.black),
        ('BACKGROUND', (0, 0), (-1, 0),  colors.lightgrey),
    ]))
    elements.append(fin_table_h)

    raw_additional = cedula.total_additional_tax
    addl_cap = Decimal('5000.00') if not is_corp else Decimal('10000.00')
    capped_additional = min(raw_additional, addl_cap)

    if not is_corp:
        fin_data = [
            [Paragraph('1. BASIC COMMUNITY TAX', styles['CedulaValue']), '',
             Paragraph(f'{cedula.basic_tax:,.2f}', styles['CedulaMoney'])],
            [Paragraph('2. ADDITIONAL COMMUNITY TAX (Taxable amount not to exceed ₱5,000.00)', styles['CedulaValue']), '', ''],
            [Paragraph('   (a) GROSS ANNUAL SALARY (₱1.00 for every ₱1,000)', styles['CedulaValue']), '',
             Paragraph(f'{cedula.additional_tax_income:,.2f}', styles['CedulaMoney'])],
            [Paragraph('   (b) GROSS RECEIPTS FROM BUSINESS (₱1.00 for every ₱1,000)', styles['CedulaValue']), '',
             Paragraph(f'{cedula.additional_tax_business:,.2f}', styles['CedulaMoney'])],
            [Paragraph('   (c) INCOME FROM REAL PROPERTY (₱1.00 for every ₱1,000)', styles['CedulaValue']), '',
             Paragraph(f'{cedula.additional_tax_property:,.2f}', styles['CedulaMoney'])],
        ]
    else:
        fin_data = [
            [Paragraph('1. BASIC COMMUNITY TAX', styles['CedulaValue']), '',
             Paragraph(f'{cedula.basic_tax:,.2f}', styles['CedulaMoney'])],
            [Paragraph('2. ADDITIONAL COMMUNITY TAX (Taxable amount not to exceed ₱10,000.00)', styles['CedulaValue']), '', ''],
            [Paragraph('   (a) ASSESSED VALUE OF REAL PROPERTY (₱2.00 for every ₱5,000)', styles['CedulaValue']), '',
             Paragraph(f'{cedula.additional_tax_property:,.2f}', styles['CedulaMoney'])],
            [Paragraph('   (b) GROSS RECEIPTS FROM BUSINESS (₱2.00 for every ₱5,000)', styles['CedulaValue']), '',
             Paragraph(f'{cedula.additional_tax_business:,.2f}', styles['CedulaMoney'])],
        ]

    fin_data.extend([
        [Paragraph('TOTAL (Basic + Capped Additional)', styles['CedulaValue']), '',
         Paragraph(f'{(cedula.basic_tax + capped_additional):,.2f}', styles['CedulaMoney'])],
        [Paragraph('INTEREST', styles['CedulaValue']), '',
         Paragraph(f'{cedula.interest:,.2f}', styles['CedulaMoney'])],
        [Paragraph('TOTAL AMOUNT PAID', styles['CedulaHeader']), '',
         Paragraph(f'₱{cedula.total_amount:,.2f}', styles['CedulaHeader'])],
    ])

    fin_table = Table(fin_data, colWidths=[3.5 * inch, 2.5 * inch, 1.5 * inch])
    fin_table.setStyle(TableStyle([
        ('BOX',       (0, 0), (-1, -1), 1,   colors.black),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('ALIGN',     (2, 0), (2, -1),  'RIGHT'),
        ('VALIGN',    (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(fin_table)
    elements.append(Spacer(1, 35))

    # Signature
    label1 = "Taxpayer's Signature" if not is_corp else 'Authorized Representative'
    sig_data = [
        [Paragraph('_______________________________', styles['CedulaValue']),
         Paragraph('_______________________________', styles['CedulaValue'])],
        [Paragraph(label1, styles['CedulaSubHeader']),
         Paragraph('Municipal/City Treasurer', styles['CedulaSubHeader'])],
    ]
    sig_table = Table(sig_data, colWidths=[3.5 * inch, 3.5 * inch])
    sig_table.setStyle(TableStyle([('ALIGN', (0, 0), (-1, -1), 'CENTER')]))
    elements.append(sig_table)

    from functools import partial
    page_func = partial(draw_page_template, certificate=certificate, is_resident=is_resident)
    doc.build(elements, onFirstPage=page_func, onLaterPages=page_func)
    buffer.seek(0)
    return buffer


# ─── Receipt PDF ──────────────────────────────────────────────────────────────

def generate_receipt_pdf(certificate):
    """Generate a 2-copy printable receipt (Resident & Barangay copies)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=letter,
        topMargin=0, bottomMargin=0.5 * inch,
        leftMargin=0.5 * inch, rightMargin=0.5 * inch,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='ReceiptHeader', fontSize=10, alignment=TA_CENTER, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='CertHeaderLabel', fontSize=10, alignment=TA_CENTER, fontName='Helvetica', leading=12))
    styles.add(ParagraphStyle(name='ReceiptTitle',  fontSize=14, alignment=TA_CENTER, fontName='Helvetica-Bold', spaceBefore=8, spaceAfter=8))
    styles.add(ParagraphStyle(name='ReceiptLabel',  fontSize=11, fontName='Helvetica-Bold'))
    styles.add(ParagraphStyle(name='ReceiptValue',  fontSize=11, fontName='Helvetica'))
    styles.add(ParagraphStyle(name='CopyLabel',     fontSize=9,  alignment=TA_RIGHT, fontName='Helvetica-Oblique', textColor=colors.grey))

    def create_receipt_elements(copy_type):
        elems = []
        elems.append(HeaderBannerFlowable())
        elems.append(Spacer(1, 0.1 * inch))
        elems.append(Paragraph(f'{copy_type} COPY', styles['CopyLabel']))
        elems.append(Paragraph('OFFICIAL RECEIPT', styles['ReceiptTitle']))
        data = [
            [Paragraph('Control Number:', styles['ReceiptLabel']), Paragraph(certificate.control_number, styles['ReceiptValue'])],
            [Paragraph('OR Number:',      styles['ReceiptLabel']), Paragraph(certificate.or_number or 'N/A', styles['ReceiptValue'])],
            [Paragraph('Date Issued:',    styles['ReceiptLabel']), Paragraph(certificate.created_at.strftime('%B %d, %Y'), styles['ReceiptValue'])],
            [Paragraph('Received From:',  styles['ReceiptLabel']), Paragraph(certificate.resident.full_name, styles['ReceiptValue'])],
            [Paragraph('Nature:',         styles['ReceiptLabel']), Paragraph(certificate.get_cert_type_display(), styles['ReceiptValue'])],
            [Paragraph('Purpose:',        styles['ReceiptLabel']), Paragraph(certificate.purpose, styles['ReceiptValue'])],
            [Paragraph('Amount Paid:',    styles['ReceiptLabel']), Paragraph(f'<b>PHP {certificate.amount_paid:,.2f}</b>', styles['ReceiptValue'])],
        ]
        t = Table(data, colWidths=[1.8 * inch, 5.2 * inch])
        t.setStyle(TableStyle([
            ('GRID',    (0, 0), (-1, -1), 0.5, colors.grey),
            ('PADDING', (0, 0), (-1, -1), 6),
            ('VALIGN',  (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elems.append(t)
        elems.append(Spacer(1, 0.35 * inch))
        sig_data = [
            [Paragraph('__________________________', styles['ReceiptHeader']),
             Spacer(1, 1),
             Paragraph('__________________________', styles['ReceiptHeader'])],
            [Paragraph('Resident Signature',          styles['CertHeaderLabel']),
             Spacer(1, 1),
             Paragraph('Barangay Collector/Treasurer', styles['CertHeaderLabel'])],
        ]
        sig_table = Table(sig_data, colWidths=[3 * inch, 1 * inch, 3 * inch])
        elems.append(sig_table)
        return elems

    all_elements = []
    all_elements.extend(create_receipt_elements('RESIDENT'))
    all_elements.append(Spacer(1, 0.2 * inch))
    all_elements.append(Paragraph('-' * 130, styles['ReceiptHeader']))
    all_elements.append(Spacer(1, 0.2 * inch))
    all_elements.extend(create_receipt_elements('BARANGAY'))

    doc.build(all_elements, onFirstPage=draw_receipt_template, onLaterPages=draw_receipt_template)
    buffer.seek(0)
    return buffer
