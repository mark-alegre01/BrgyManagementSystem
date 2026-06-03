import csv
from datetime import date, timedelta
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import io

from residents.models import Resident
from payments.models import Payment, OfficialReceipt
from certifications.models import CertificateRequest, FirstTimeJobseekerRoster, RA11261Application, Certificate

def ra11261_apply(request):
    """Resident submits application via a Django form."""
    if request.method == 'POST':
        resident_id = request.POST.get('resident')
        declaration = request.POST.get('declaration_confirmed')
        docs = request.FILES.get('uploaded_docs')

        if not resident_id or not declaration or not docs:
            messages.error(request, "Please fill in all required fields and upload the document.")
            return redirect('certifications:ra11261_apply')

        try:
            resident = Resident.objects.get(id=resident_id)
        except Resident.DoesNotExist:
            messages.error(request, "Resident not found.")
            return redirect('certifications:ra11261_apply')

        application = RA11261Application(
            resident=resident,
            declaration_confirmed=(declaration == 'on' or declaration == 'true'),
            uploaded_docs=docs
        )

        # Auto-validation Step 1: Check existing availment
        if FirstTimeJobseekerRoster.objects.filter(resident=resident).exists():
            application.status = 'REJECTED'
            application.rejection_reason = "Already availed RA 11261 benefit"
            application.save()
            messages.error(request, f"Application Auto-Rejected: {application.rejection_reason}")
            return redirect('certifications:ra11261_apply')

        # Auto-validation Step 2: Check residency requirement (180 days)
        if resident.residency_start_date:
            days_resident = (date.today() - resident.residency_start_date).days
            if days_resident < 180:
                application.status = 'REJECTED'
                application.rejection_reason = "Residency requirement not met (minimum 6 months)"
                application.save()
                messages.error(request, f"Application Auto-Rejected: {application.rejection_reason}")
                return redirect('certifications:ra11261_apply')

        # Passed auto-checks
        application.status = 'FOR_REVIEW'
        application.save()
        messages.success(request, "Application submitted successfully. It is now FOR REVIEW.")
        return redirect('certifications:ra11261_apply')

    return render(request, 'certifications/ra11261_apply.html')


@login_required
def ra11261_admin_list(request):
    """Admin views list of applications."""
    status_filter = request.GET.get('status', 'ALL')
    search = request.GET.get('search', '')

    applications = RA11261Application.objects.select_related('resident').all()

    if status_filter != 'ALL':
        applications = applications.filter(status=status_filter)
    
    if search:
        applications = applications.filter(resident__first_name__icontains=search) | \
                       applications.filter(resident__last_name__icontains=search)

    context = {
        'applications': applications,
        'status_filter': status_filter,
        'search': search,
    }
    return render(request, 'certifications/ra11261_admin_list.html', context)


@login_required
def ra11261_admin_review(request, pk):
    """Admin approves or rejects the application via POST."""
    if request.method == 'POST':
        application = get_object_or_404(RA11261Application, pk=pk)
        new_status = request.POST.get('status')
        rejection_reason = request.POST.get('rejection_reason', '')

        if new_status not in ['APPROVED', 'REJECTED']:
            messages.error(request, "Invalid status.")
            return redirect('certifications:ra11261_admin_list')

        if new_status == 'APPROVED':
            if FirstTimeJobseekerRoster.objects.filter(resident=application.resident).exists():
                messages.error(request, "Resident already has an active or expired roster record.")
                return redirect('certifications:ra11261_admin_list')

            # Issue Certificate Request & waive fee
            cert_req = CertificateRequest.objects.filter(resident=application.resident, is_first_time_jobseeker=True, status='pending').first()
            if not cert_req:
                cert_req = CertificateRequest.objects.create(
                    resident=application.resident,
                    cert_type='clearance', 
                    purpose='First Time Jobseeker (RA 11261)',
                    is_first_time_jobseeker=True,
                    status='issued',
                    processed_by=request.user,
                    processed_at=timezone.now()
                )
            else:
                cert_req.status = 'issued'
                cert_req.processed_by = request.user
                cert_req.processed_at = timezone.now()
                cert_req.save()

            if not cert_req.payment:
                payment = Payment.objects.create(amount=0, status='paid', method='waived', verified_by=request.user, waive_reason='RA 11261 Benefit Waived')
                cert_req.payment = payment
                cert_req.save()
            else:
                payment = cert_req.payment
                payment.amount = 0
                payment.status = 'paid'
                payment.method = 'waived'
                payment.waive_reason = 'RA 11261 Benefit Waived'
                payment.save()

            if not payment.official_receipt:
                receipt = OfficialReceipt.objects.create(
                    or_number=f"EXEMPT-RA11261-{cert_req.id}", 
                    resident=application.resident,
                    amount=0, 
                    particulars="RA 11261 Benefit Waived", 
                    issued_by=request.user
                )
                payment.official_receipt = receipt
                payment.save()
            else:
                receipt = payment.official_receipt
                receipt.or_number = f"EXEMPT-RA11261-{cert_req.id}"
                receipt.amount = 0
                receipt.particulars = "RA 11261 Benefit Waived"
                receipt.save()

            cert_date = date.today()
            expiry_date = cert_date + timedelta(days=365)
            
            FirstTimeJobseekerRoster.objects.create(
                resident=application.resident,
                certificate_request=cert_req,
                certification_date=cert_date,
                expiry_date=expiry_date,
                added_by=request.user
            )

            from certifications.views import generate_control_number
            Certificate.objects.get_or_create(
                resident=application.resident,
                certificate_request=cert_req,
                defaults={
                    'issued_by': request.user, 
                    'status': 'issued',
                    'control_number': generate_control_number(cert_req.cert_type)
                }
            )
            messages.success(request, "Application APPROVED and Roster updated.")

        elif new_status == 'REJECTED':
            if not rejection_reason:
                messages.error(request, "Rejection reason is required.")
                return redirect('certifications:ra11261_admin_list')
            messages.warning(request, "Application REJECTED.")

        application.status = new_status
        application.rejection_reason = rejection_reason if new_status == 'REJECTED' else None
        application.save()

    return redirect('certifications:ra11261_admin_list')


@login_required
def ra11261_admin_roster(request):
    """Admin views full roster."""
    search = request.GET.get('search', '')
    roster = FirstTimeJobseekerRoster.objects.select_related('resident').all()
    
    if search:
        roster = roster.filter(resident__first_name__icontains=search) | \
                 roster.filter(resident__last_name__icontains=search)

    active_count = 0
    expired_count = 0
    today = date.today()
    for r in roster:
        if r.expiry_date >= today:
            active_count += 1
        else:
            expired_count += 1

    # Fetch all residents who are NOT already in the roster, so admin can select them.
    roster_resident_ids = roster.values_list('resident_id', flat=True)
    available_residents = Resident.objects.exclude(id__in=roster_resident_ids).order_by('last_name')

    context = {
        'roster': roster,
        'search': search,
        'total_availed': roster.count(),
        'active_count': active_count,
        'expired_count': expired_count,
        'available_residents': available_residents,
    }
    return render(request, 'certifications/ra11261_admin_roster.html', context)

@login_required
def ra11261_admin_roster_add(request):
    """Admin manually adds a walk-in resident to the Roster."""
    if request.method == 'POST':
        resident_id = request.POST.get('resident_id')
        if not resident_id:
            messages.error(request, "Please select a resident.")
            return redirect('certifications:ra11261_admin_roster')

        resident = get_object_or_404(Resident, pk=resident_id)

        if FirstTimeJobseekerRoster.objects.filter(resident=resident).exists():
            messages.error(request, "Resident already exists in the RA 11261 roster.")
            return redirect('certifications:ra11261_admin_roster')

        # To keep data consistent, we create an approved RA11261Application representing the walk-in
        application = RA11261Application.objects.create(
            resident=resident,
            declaration_confirmed=True, # Assumed they signed it physically
            status='APPROVED'
        )

        # Issue Certificate Request & waive fee
        cert_req = CertificateRequest.objects.create(
            resident=resident,
            cert_type='clearance', 
            purpose='First Time Jobseeker (RA 11261) - Walk In',
            is_first_time_jobseeker=True,
            status='issued',
            processed_by=request.user,
            processed_at=timezone.now()
        )

        payment = Payment.objects.create(amount=0, status='paid', method='waived', verified_by=request.user, waive_reason='RA 11261 Benefit Waived (Walk-In)')
        cert_req.payment = payment
        cert_req.save()

        receipt = OfficialReceipt.objects.create(
            or_number=f"EXEMPT-RA11261-{cert_req.id}", 
            resident=resident,
            amount=0, 
            particulars="RA 11261 Benefit Waived (Walk-In)", 
            issued_by=request.user
        )
        payment.official_receipt = receipt
        payment.save()

        cert_date = date.today()
        expiry_date = cert_date + timedelta(days=365)
        
        FirstTimeJobseekerRoster.objects.create(
            resident=resident,
            certificate_request=cert_req,
            certification_date=cert_date,
            expiry_date=expiry_date,
            added_by=request.user
        )

        from certifications.views import generate_control_number
        Certificate.objects.create(
            resident=resident,
            certificate_request=cert_req,
            issued_by=request.user,
            status='issued',
            control_number=generate_control_number(cert_req.cert_type)
        )
        messages.success(request, f"Successfully added {resident.full_name} to the RA 11261 Roster.")
        
    return redirect('certifications:ra11261_admin_roster')


@login_required
def ra11261_export_csv(request):
    """Export roster to CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="ra11261_roster.csv"'

    writer = csv.writer(response)
    writer.writerow(['Resident Name', 'Certification Date', 'Expiry Date', 'Status', 'Added By'])

    roster = FirstTimeJobseekerRoster.objects.select_related('resident', 'added_by').all()
    today = date.today()

    for r in roster:
        status_text = 'Active' if r.expiry_date >= today else 'Expired'
        added_by = r.added_by.username if r.added_by else 'System'
        writer.writerow([
            r.resident.full_name,
            r.certification_date,
            r.expiry_date,
            status_text,
            added_by
        ])

    return response


def ra11261_certification_pdf(request, pk):
    """Generate PDF for the RA 11261 Certification — matching the standard certificate layout."""
    import os
    from functools import partial
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib import colors
    from django.conf import settings as django_settings
    from certifications.utils import draw_watermark
    from officials.models import Official

    try:
        application = RA11261Application.objects.get(pk=pk)
        roster = FirstTimeJobseekerRoster.objects.get(resident=application.resident)
    except (RA11261Application.DoesNotExist, FirstTimeJobseekerRoster.DoesNotExist):
        return HttpResponse("Certification not found or not approved yet.", status=404)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                            topMargin=0.3 * inch, bottomMargin=0.3 * inch,
                            leftMargin=0.5 * inch, rightMargin=0.5 * inch)

    styles = getSampleStyleSheet()

    # Custom Styles (same as generate_certificate_pdf)
    styles.add(ParagraphStyle(name='CertHeaderLabel', fontSize=10, alignment=TA_CENTER,
                               fontName='Helvetica', leading=12))
    styles.add(ParagraphStyle(name='CertHeaderBrgy', fontSize=12, alignment=TA_CENTER,
                               fontName='Helvetica-Bold', leading=14))
    styles.add(ParagraphStyle(name='CertOffice', fontSize=16, alignment=TA_CENTER,
                               spaceBefore=20, spaceAfter=10, fontName='Times-Bold'))
    styles.add(ParagraphStyle(name='CertTitleLarge', fontSize=22, alignment=TA_CENTER,
                               spaceAfter=25, fontName='Helvetica-Bold', leading=26))
    styles.add(ParagraphStyle(name='CertSubTitle', fontSize=13, alignment=TA_CENTER,
                               spaceAfter=20, fontName='Helvetica-Oblique', leading=16))
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

    # ── HEADER (same as other certificates) ──────────────────────────
    sico_logo_path = os.path.join(django_settings.BASE_DIR, 'static/images/sico_sico_logo.jpg')
    bagong_pilipinas_path = os.path.join(django_settings.BASE_DIR, 'static/images/bagong_pilipinas.png')
    gigaquit_logo_path = os.path.join(django_settings.BASE_DIR, 'static/images/gigaquit_logo.png')

    logo_w = 0.85 * inch
    logo_h = 0.85 * inch

    img_sico = Image(sico_logo_path, width=logo_w, height=logo_h, kind='proportional') if os.path.exists(sico_logo_path) else Spacer(logo_w, logo_h)
    img_bagong = Image(bagong_pilipinas_path, width=1.3*inch, height=0.85*inch, kind='proportional') if os.path.exists(bagong_pilipinas_path) else Spacer(1.3*inch, logo_h)
    img_gigaquit = Image(gigaquit_logo_path, width=logo_w, height=logo_h, kind='proportional') if os.path.exists(gigaquit_logo_path) else Spacer(logo_w, logo_h)

    brgy_name = getattr(django_settings, 'BARANGAY_NAME', 'Sico-Sico')
    municipality = getattr(django_settings, 'BARANGAY_MUNICIPALITY', 'Gigaquit')
    province = getattr(django_settings, 'BARANGAY_PROVINCE', 'Surigao del Norte')

    header_brgy_title = brgy_name.upper() if "BARANGAY" in brgy_name.upper() else f"BARANGAY {brgy_name.upper()}"

    center_text = [
        Paragraph('REPUBLIC OF THE PHILIPPINES', styles['CertHeaderLabel']),
        Paragraph(f'Province of {province}', styles['CertHeaderLabel']),
        Paragraph(f'Municipality of {municipality}', styles['CertHeaderLabel']),
        Paragraph(header_brgy_title, styles['CertHeaderBrgy']),
    ]

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

    elements.append(header_table)
    elements.append(Paragraph('OFFICE OF THE SANGGUNIANG BARANGAY', styles['CertOffice']))
    elements.append(Paragraph('BARANGAY CERTIFICATION', styles['CertTitleLarge']))
    elements.append(Paragraph('First Time Jobseekers Assistance Act (RA 11261)', styles['CertSubTitle']))

    # ── BODY ─────────────────────────────────────────────────────────
    resident = application.resident
    display_brgy = brgy_name if "BARANGAY" in brgy_name.upper() else f"Barangay {brgy_name}"

    elements.append(Paragraph('TO WHOM IT MAY CONCERN;', styles['CertToWhom']))

    body_text = (
        f"This is to certify that <b>{resident.full_name.upper()}</b>, "
        f"{resident.age} years old, {resident.get_civil_status_display()}, Filipino, "
        f"a resident of {display_brgy}, {municipality}, {province}, "
        f"is a qualified <b>First Time Jobseeker</b> under Republic Act No. 11261, "
        f"otherwise known as the \"First Time Jobseekers Assistance Act\"."
    )
    elements.append(Paragraph(body_text, styles['CertBody']))

    benefit_text = (
        "The above-named person has not previously availed of the benefits under RA 11261 "
        "and is hereby granted exemption from the payment of fees and charges for the "
        "issuance of this Barangay Certification."
    )
    elements.append(Paragraph(benefit_text, styles['CertBody']))

    conclusion_text = (
        "This certification is issued upon the request of the above-named person "
        "in compliance with RA 11261 for employment purposes."
    )
    elements.append(Paragraph(conclusion_text, styles['CertBody']))

    # ── ISSUED DATE ──────────────────────────────────────────────────
    def get_ordinal(n):
        if 11 <= (n % 100) <= 13:
            return f"{n}th"
        return f"{n}{['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]}"

    cert_date = roster.certification_date
    issued_date_text = (
        f"Given this <b>{get_ordinal(cert_date.day)}</b> day of "
        f"<b>{cert_date.strftime('%B')}, {cert_date.year}</b>, "
        f"at the Office of Punong Barangay of {display_brgy}, {municipality}, Surigao del Norte."
    )
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(issued_date_text, styles['CertBody']))

    validity_text = f"<b>Valid until: {roster.expiry_date.strftime('%B %d, %Y')}</b>"
    elements.append(Paragraph(validity_text, styles['CertBody']))

    elements.append(Spacer(1, 40))

    # ── CAPTAIN SIGNATURE ────────────────────────────────────────────
    captain = Official.objects.filter(position='captain', status='active').first()
    captain_name = f"HON. {captain.resident.full_name.upper()}" if captain else getattr(django_settings, 'BARANGAY_CAPTAIN', 'NO ACTIVE CAPTAIN')
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

    # ── WARNING ──────────────────────────────────────────────────────
    elements.append(Spacer(1, 20))
    elements.append(Paragraph('\u201cNOT VALID WITHOUT SEAL\u201d', styles['CertWarning']))

    # ── BUILD PDF ────────────────────────────────────────────────────
    watermark_func = partial(draw_watermark, is_resident=False)
    doc.build(elements, onFirstPage=watermark_func, onLaterPages=watermark_func)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="RA11261_{resident.full_name}.pdf"'
    return response

