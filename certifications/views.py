from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, FileResponse, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Certificate, Cedula, CertificateRequest
from officials.models import Official
from residents.models import Resident
from datetime import date
from decimal import Decimal
import uuid
from core.models import SystemSettings


def generate_control_number(cert_type):
    """Generate unique control number for certificate following Prefix-Sequence-Year."""
    prefix_map = {
        'clearance': 'BC',
        'residency': 'CR',
        'indigency': 'CI',
        'good_moral': 'GM',
        'business_permit': 'BP',
        'comelec': 'CC',
        'cedula': 'CTC',
        'late_registration': 'LR',
    }
    prefix = prefix_map.get(cert_type, 'CERT')
    year = date.today().year
    
    # Count all certificates of this type in the current year
    count = Certificate.objects.filter(
        certificate_request__cert_type=cert_type,
        created_at__year=year
    ).count() + 1
    
    return f"{prefix}-{count:03d}-{year}"


def generate_or_number():
    """Generate the next OR number by incrementing the last numeric one from OfficialReceipt."""
    from payments.models import OfficialReceipt
    import re
    receipts = OfficialReceipt.objects.order_by('-id')[:20]
    base_or = None
    for r in receipts:
        if re.search(r'\d+$', r.or_number):
            base_or = r.or_number
            break
    if not base_or:
        return OfficialReceipt.generate_next_or_number()
    try:
        match = re.search(r'(\d+)$', base_or)
        number_str = match.group(1)
        number = int(number_str)
        prefix = base_or[:match.start()]
        return f"{prefix}{number + 1:0{len(number_str)}d}"
    except Exception:
        return OfficialReceipt.generate_next_or_number()


def generate_ctc_number():
    """Generate the next CTC (Cedula) number."""
    from certifications.models import Cedula
    last_cedula = Cedula.objects.order_by('-id').first()
    year = date.today().year
    
    if not last_cedula or not last_cedula.ctc_number:
        return f"CCIC{year}001"
        
    import re
    match = re.search(r'(\d+)$', last_cedula.ctc_number)
    if match:
        number_str = match.group(1)
        # Handle cases where the year might be part of the number string
        # e.g., 2026001. If it's too long, we might just want the last 3 digits.
        # But let's assume the prefix is constant for the year
        prefix = last_cedula.ctc_number[:match.start()]
        number = int(number_str)
        return f"{prefix}{number + 1:0{len(number_str)}d}"
        
    return f"CCIC{year}001"


def get_certificate_rate(cert_type):
    """Return the standard rate for a certificate type."""
    rates = {
        'clearance': Decimal('100.00'),
        'residency': Decimal('50.00'),
        'indigency': Decimal('0.00'),
        'good_moral': Decimal('50.00'),
        'business_permit': Decimal('500.00'),
        'comelec': Decimal('50.00'),
        'cedula': Decimal('0.00'),  # Calculated dynamically
        'late_registration': Decimal('50.00'),
    }
    return rates.get(cert_type, Decimal('50.00'))


@login_required
def get_next_numbers(request):
    """AJAX view to suggest next Control and OR numbers."""
    cert_type = request.GET.get('type')
    if not cert_type:
        return JsonResponse({})
        
    next_control = generate_control_number(cert_type)
    next_or = generate_or_number()
    next_ctc = generate_ctc_number() if cert_type == 'cedula' else ""
    rate = get_certificate_rate(cert_type)
            
    return JsonResponse({
        'control_number': next_control,
        'or_number': next_or,
        'ctc_number': next_ctc,
        'rate': format(rate, '.2f')
    })


@login_required
def certificate_list(request):
    """List all certificates."""
    query = request.GET.get('q', '')
    cert_type = request.GET.get('type', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    certs = Certificate.objects.select_related('resident', 'issued_by')

    if query:
        certs = certs.filter(
            Q(control_number__icontains=query) |
            Q(resident__first_name__icontains=query) |
            Q(resident__last_name__icontains=query)
        )
    if cert_type:
        certs = certs.filter(cert_type=cert_type)
    if date_from:
        certs = certs.filter(date_issued__gte=date_from)
    if date_to:
        certs = certs.filter(date_issued__lte=date_to)

    # Residents can only see their own certificates
    role = 'staff'
    try:
        role = request.user.profile.role
    except Exception:
        pass

    if role == 'resident':
        try:
            own_resident = request.user.profile.resident
            if own_resident:
                certs = Certificate.objects.filter(resident=own_resident).select_related('resident', 'issued_by')
            else:
                certs = Certificate.objects.none()
        except Exception:
            certs = Certificate.objects.none()

        paginator = Paginator(certs, 25)
        page = request.GET.get('page')
        certs = paginator.get_page(page)
        return render(request, 'certifications/list.html', {
            'certificates': certs,
            'query': '',
            'selected_type': '',
            'cert_types': Certificate.TYPE_CHOICES,
            'is_resident_view': True,
        })

    paginator = Paginator(certs, 25)
    page = request.GET.get('page')
    certs = paginator.get_page(page)

    context = {
        'certificates': certs,
        'query': query,
        'selected_type': cert_type,
        'cert_types': Certificate.TYPE_CHOICES,
    }
    return render(request, 'certifications/list.html', context)


@login_required
def certificate_issue(request):
    """Issue a new certificate – admin/staff only."""
    # Residents cannot issue certificates – refer to barangay office
    role = 'staff'
    try:
        role = request.user.profile.role
    except Exception:
        pass

    if role == 'resident':
        messages.error(request, "Certificate issuance must be done at the barangay office. Please visit us in person.")
        return redirect('core:dashboard')

    if request.method == 'POST':
        cert_type = request.POST.get('cert_type')
        resident_id = request.POST.get('resident')
        resident = get_object_or_404(Resident, pk=resident_id)

        def to_decimal(val):
            if not val: return Decimal('0.00')
            try:
                clean_val = str(val).replace(',', '')
                return Decimal(clean_val)
            except:
                return Decimal('0.00')

        control_number = request.POST.get('control_number') or generate_control_number(cert_type)

        # Build or find a backing CertificateRequest so Certificate can reference it
        cert_req, _ = CertificateRequest.objects.get_or_create(
            resident=resident,
            cert_type=cert_type,
            status='pending',
            defaults={
                'purpose': request.POST.get('purpose', ''),
                'business_name': request.POST.get('business_name', ''),
                'business_address': request.POST.get('business_address', ''),
                'business_type': request.POST.get('business_type', ''),
                'child_name': request.POST.get('child_name', ''),
                'child_birth_date': request.POST.get('child_birth_date') or None,
                'child_birth_place': request.POST.get('child_birth_place', ''),
                'father_name': request.POST.get('father_name', ''),
                'mother_name': request.POST.get('mother_name', ''),
            }
        )

        cert = Certificate(
            control_number=control_number,
            resident=resident,
            certificate_request=cert_req,
            business_name=request.POST.get('business_name', ''),
            business_address=request.POST.get('business_address', ''),
            business_type=request.POST.get('business_type', ''),
            issued_by=request.user,
            status='issued',
        )

        if cert_type == 'late_registration':
            cert.child_name = request.POST.get('child_name', '')
            cert.child_birth_date = request.POST.get('child_birth_date') or None
            cert.child_birth_place = request.POST.get('child_birth_place', '')
            cert.father_name = request.POST.get('father_name', '')
            cert.mother_name = request.POST.get('mother_name', '')

        cert.save()

        # Mark request as issued
        cert_req.status = 'issued'
        cert_req.processed_by = request.user
        from django.utils import timezone as tz
        cert_req.processed_at = tz.now()
        cert_req.save()

        if cert_type == 'cedula':
            from certifications.models import Cedula
            Cedula.objects.create(
                certificate=cert,
                ctc_number=request.POST.get('ctc_number'),
                taxpayer_type=request.POST.get('taxpayer_type', 'individual'),
                place_of_issue=request.POST.get('place_of_issue', 'Sico-Sico, Gigaquit'),
                height=request.POST.get('height', ''),
                weight=request.POST.get('weight', ''),
                raw_taxable_property=to_decimal(request.POST.get('raw_taxable_property')),
                raw_taxable_business=to_decimal(request.POST.get('raw_taxable_business')),
                raw_taxable_income=to_decimal(request.POST.get('raw_taxable_income')),
                basic_tax=to_decimal(request.POST.get('basic_tax')),
                additional_tax_property=to_decimal(request.POST.get('additional_tax_property')),
                additional_tax_business=to_decimal(request.POST.get('additional_tax_business')),
                additional_tax_income=to_decimal(request.POST.get('additional_tax_income')),
                interest=to_decimal(request.POST.get('interest'))
            )

        messages.success(request, f'{cert.get_cert_type_display()} issued for {resident.full_name}. Control #: {cert.control_number}')
        return redirect('certifications:view', pk=cert.pk)

    residents = Resident.objects.filter(is_active=True)
    query = request.GET.get('q', '')
    if query:
        residents = residents.filter(
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query)
        )
    context = {
        'residents': residents[:50],
        'cert_types': Certificate.TYPE_CHOICES,
        'query': query,
    }
    return render(request, 'certifications/issue.html', context)


@login_required
def certificate_view(request, pk):
    """View certificate details."""
    cert = get_object_or_404(Certificate.objects.select_related('resident', 'issued_by'), pk=pk)
    return render(request, 'certifications/view.html', {'certificate': cert})


@login_required
def certificate_pdf(request, pk):
    """Generate and download certificate PDF."""
    from .utils import generate_certificate_pdf
    cert = get_object_or_404(Certificate.objects.select_related('resident'), pk=pk)
    role = 'resident'
    try:
        role = request.user.profile.role
    except Exception:
        pass
    
    pdf_buffer = generate_certificate_pdf(cert, is_resident=(role == 'resident'))
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{cert.control_number}.pdf"'
    return response


@login_required
def certificate_search(request):
    """Search certificates by control number."""
    control = request.GET.get('control', '')
    cert = None
    if control:
        cert = Certificate.objects.filter(control_number=control).select_related('resident').first()
    return render(request, 'certifications/search.html', {
        'certificate': cert,
        'control': control,
    })


@login_required
def check_uniqueness(request):
    """AJAX view to check if an OR Number or CTC Number is already taken."""
    from django.http import JsonResponse
    from .models import Certificate, Cedula
    
    field = request.GET.get('field')
    value = request.GET.get('value')
    
    if not field or not value:
        return JsonResponse({'available': True})
    
    if field == 'or_number':
        from payments.models import OfficialReceipt
        exists = OfficialReceipt.objects.filter(or_number=value).exists()
    elif field == 'ctc_number':
        exists = Cedula.objects.filter(ctc_number=value).exists()
    else:
        exists = False
        
    return JsonResponse({'available': not exists})
@login_required
def certificate_receipt_pdf(request, pk):
    """Generate and download transaction receipt PDF."""
    from .utils import generate_receipt_pdf
    cert = get_object_or_404(Certificate.objects.select_related('resident'), pk=pk)
    pdf_buffer = generate_receipt_pdf(cert)
    response = HttpResponse(pdf_buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="RECEIPT-{cert.control_number}.pdf"'
    return response


@login_required
def certificate_delete(request, pk):
    """Delete a certificate (POST only) – admin/staff only."""
    role = 'staff'
    try:
        role = request.user.profile.role
    except Exception:
        pass
    if role == 'resident':
        messages.error(request, "You do not have permission to perform this action.")
        return redirect('certifications:list')
    cert = get_object_or_404(Certificate, pk=pk)
    if request.method == 'POST':
        control_number = cert.control_number
        cert.delete()
        messages.success(request, f'Certificate {control_number} has been deleted.')
    return redirect('certifications:list')


# ─── Certificate Requests ────────────────────────────────────────────────────

@login_required
def request_certificate(request):
    """Resident submits a certificate request."""
    role = 'staff'
    own_resident = None
    try:
        role = request.user.profile.role
        own_resident = request.user.profile.resident
    except Exception:
        pass

    if role != 'resident':
        messages.error(request, "This page is for residents only.")
        return redirect('core:dashboard')

    if own_resident is None:
        messages.error(request, "Your account is not linked to a resident record. Please contact the barangay office.")
        return redirect('core:dashboard')

    if request.method == 'POST':
        cert_type = request.POST.get('cert_type')
        purpose = request.POST.get('purpose', '').strip()

        if not cert_type or not purpose:
            messages.error(request, "Please fill in all required fields.")
        elif CertificateRequest.objects.filter(resident=own_resident, cert_type=cert_type, status='pending').exists():
            messages.warning(request, "You already have a pending request for this certificate type.")
        else:
            cert_req = CertificateRequest.objects.create(
                resident=own_resident,
                cert_type=cert_type,
                purpose=purpose,
                
                # Business fields
                business_name=request.POST.get('business_name', ''),
                business_address=request.POST.get('business_address', ''),
                business_type=request.POST.get('business_type', ''),
                
                # Cedula fields
                taxpayer_type=request.POST.get('taxpayer_type', ''),
                place_of_issue=request.POST.get('place_of_issue', ''),
                height=request.POST.get('height', ''),
                weight=request.POST.get('weight', ''),
                raw_taxable_property=Decimal(request.POST.get('raw_taxable_property') or '0.00'),
                raw_taxable_business=Decimal(request.POST.get('raw_taxable_business') or '0.00'),
                raw_taxable_income=Decimal(request.POST.get('raw_taxable_income') or '0.00'),

                # Late Registration details
                child_name=request.POST.get('child_name', ''),
                child_birth_date=request.POST.get('child_birth_date') or None,
                child_birth_place=request.POST.get('child_birth_place', ''),
                father_name=request.POST.get('father_name', ''),
                mother_name=request.POST.get('mother_name', ''),
            )
            messages.success(request, f"Your request for a {cert_type} has been submitted! Tracking Code: {cert_req.tracking_code}")
            return redirect('payments:choose_payment', request_id=cert_req.id)

    return render(request, 'certifications/request_form.html', {
        'cert_types': Certificate.TYPE_CHOICES,
    })


@login_required
def my_requests(request):
    """Resident's own certificate request history."""
    role = 'staff'
    own_resident = None
    try:
        role = request.user.profile.role
        own_resident = request.user.profile.resident
    except Exception:
        pass

    if role != 'resident':
        return redirect('certifications:request_list')

    reqs = CertificateRequest.objects.filter(resident=own_resident).order_by('-created_at')
    return render(request, 'certifications/my_requests.html', {'requests': reqs})


@login_required
def request_list(request):
    """Admin view: list all certificate requests with status tabs."""
    role = 'staff'
    try:
        role = request.user.profile.role
    except Exception:
        pass

    if role == 'resident':
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')

    status_filter = request.GET.get('status', 'pending')
    reqs = CertificateRequest.objects.select_related('resident', 'processed_by').all()
    if status_filter:
        reqs = reqs.filter(status=status_filter)

    paginator = Paginator(reqs, 20)
    reqs = paginator.get_page(request.GET.get('page'))

    pending_count = CertificateRequest.objects.filter(status='pending').count()

    return render(request, 'certifications/request_list.html', {
        'requests': reqs,
        'status_filter': status_filter,
        'pending_count': pending_count,
    })


@login_required
def fulfill_request(request, pk):
    """Admin: fulfill a pending request by issuing a certificate."""
    from django.utils import timezone
    from core.models import Notification

    role = 'staff'
    try:
        role = request.user.profile.role
    except Exception:
        pass

    if role == 'resident':
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')

    cert_request = get_object_or_404(CertificateRequest, pk=pk)

    if cert_request.status != 'pending':
        messages.error(request, "This request has already been processed.")
        return redirect('certifications:request_list')

    # Bypassed payment status blocker to allow admin to open fulfillment form
    if not hasattr(cert_request, 'payment') or not cert_request.payment:
        # If for some reason no payment object exists, we should probably create one or handle it
        pass

    if request.method == 'POST':
        def to_decimal(val):
            if not val:
                return Decimal('0.00')
            try:
                return Decimal(str(val).replace(',', ''))
            except Exception:
                return Decimal('0.00')

        control_number = request.POST.get('control_number') or generate_control_number(cert_request.cert_type)

        cert = Certificate.objects.create(
            control_number=control_number,
            resident=cert_request.resident,
            certificate_request=cert_request,
            issued_by=request.user,
            status='issued',
            business_name=request.POST.get('business_name', cert_request.business_name),
            business_address=request.POST.get('business_address', cert_request.business_address),
            business_type=request.POST.get('business_type', cert_request.business_type),
        )

        if cert.cert_type == 'cedula':
            from certifications.models import Cedula
            ctc_number = request.POST.get('ctc_number', '')
            Cedula.objects.create(
                certificate=cert,
                ctc_number=ctc_number,
                taxpayer_type=request.POST.get('taxpayer_type', 'individual'),
                place_of_issue=request.POST.get('place_of_issue', 'Sico-Sico, Gigaquit'),
                height=request.POST.get('height', ''),
                weight=request.POST.get('weight', ''),
                raw_taxable_property=to_decimal(request.POST.get('raw_taxable_property', 0)),
                raw_taxable_business=to_decimal(request.POST.get('raw_taxable_business', 0)),
                raw_taxable_income=to_decimal(request.POST.get('raw_taxable_income', 0)),
            )

        cert_request.status = 'issued'
        # cert_request.issued_certificate is already linked via Certificate.certificate_request FK
        cert_request.processed_by = request.user
        cert_request.processed_at = timezone.now()
        cert_request.save()

        # Mark payment as paid upon issuance if it was unpaid/pending
        if hasattr(cert_request, 'payment') and cert_request.payment:
            if cert_request.payment.status not in ['paid', 'waived']:
                cert_request.payment.status = 'paid'
                cert_request.payment.save()

        # Notify resident
        try:
            resident_user = cert_request.resident.user_profile.user
            Notification.objects.create(
                user=resident_user,
                message=f'Your request for a {cert_request.get_cert_type_display()} has been issued! Control #: {cert.control_number}.',
                link=f'/certifications/{cert.pk}/',
            )
        except Exception:
            pass

        messages.success(request, f'Certificate {cert.control_number} issued and resident notified.')
        return redirect('certifications:request_list')

    # GET: show the fulfillment form
    return render(request, 'certifications/fulfill_form.html', {
        'cert_request': cert_request,
        'suggested_control': generate_control_number(cert_request.cert_type),
        'suggested_or': generate_or_number(),
        'suggested_ctc': generate_ctc_number() if cert_request.cert_type == 'cedula' else "",
        'base_amount': get_certificate_rate(cert_request.cert_type),
    })


@login_required
def reject_request(request, pk):
    """Admin: reject a pending certificate request."""
    from django.utils import timezone
    from core.models import Notification

    role = 'staff'
    try:
        role = request.user.profile.role
    except Exception:
        pass

    if role == 'resident':
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')

    cert_request = get_object_or_404(CertificateRequest, pk=pk)

    if cert_request.status != 'pending':
        messages.error(request, "This request has already been processed.")
        return redirect('certifications:request_list')

    if request.method == 'POST':
        notes = request.POST.get('notes', '').strip()
        cert_request.status = 'rejected'
        cert_request.notes = notes
        cert_request.processed_by = request.user
        cert_request.processed_at = timezone.now()
        cert_request.save()

        # Notify resident
        try:
            resident_user = cert_request.resident.user_profile.user
            note_text = f' Reason: {notes}' if notes else ''
            Notification.objects.create(
                user=resident_user,
                message=f'Your request for a {cert_request.get_cert_type_display()} was not approved.{note_text}',
                link='/certifications/my-requests/',
            )
        except Exception:
            pass

        messages.warning(request, f'Request #{pk} has been rejected.')
        return redirect('certifications:request_list')

    return redirect('certifications:request_list')


@login_required
def virtual_certificate(request, pk):
    """View certificate as a 'virtual' document (card/styled)."""
    cert = get_object_or_404(Certificate.objects.select_related('resident', 'issued_by'), pk=pk)
    
    # Check if resident owns this certificate
    try:
        role = request.user.profile.role
        if role == 'resident':
            if cert.resident != request.user.profile.resident:
                messages.error(request, "Permission denied.")
                return redirect('core:dashboard')
    except Exception:
        pass

    settings = SystemSettings.objects.first()
    
    # Logic for current captain
    captain = Official.objects.filter(position='captain', status='active').first()
    captain_name = captain.resident.full_name if captain else "OFFICIAL CAPTAIN NAME"
        
    role = 'resident'
    try:
        role = request.user.profile.role
    except Exception:
        pass

    return render(request, 'certifications/virtual_certificate.html', {
        'certificate': cert,
        'settings': settings,
        'captain_name': captain_name,
        'user_role': role
    })
