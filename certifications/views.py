from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, FileResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Certificate, Cedula
from residents.models import Resident
from datetime import date
from decimal import Decimal
import uuid


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
        cert_type=cert_type,
        created_at__year=year
    ).count() + 1
    
    return f"{prefix}-{count:03d}-{year}"


@login_required
def get_next_numbers(request):
    """AJAX view to suggest next Control and OR numbers."""
    from django.http import JsonResponse
    import re
    
    cert_type = request.GET.get('type')
    if not cert_type:
        return JsonResponse({})
        
    next_control = generate_control_number(cert_type)
    
    # Logic for next OR Number: Find highest numeric OR number
    latest_or_cert = Certificate.objects.exclude(or_number__in=[None, '', 'EXEMPT', 'FREE']).order_by('-id').first()
    next_or = ""
    if latest_or_cert and latest_or_cert.or_number:
        # Try to find numeric part and increment it
        match = re.search(r'(\d+)$', latest_or_cert.or_number)
        if match:
            num_str = match.group(1)
            next_num = int(num_str) + 1
            prefix = latest_or_cert.or_number[:match.start()]
            next_or = f"{prefix}{next_num:0{len(num_str)}d}"
        else:
            next_or = latest_or_cert.or_number # Fallback to same if not incrementable
            
    return JsonResponse({
        'control_number': next_control,
        'or_number': next_or
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
    """Issue a new certificate."""
    if request.method == 'POST':
        cert_type = request.POST.get('cert_type')
        resident_id = request.POST.get('resident')
        resident = get_object_or_404(Resident, pk=resident_id)

        # Validation for uniqueness
        or_number = request.POST.get('or_number')
        if or_number:
            if Certificate.objects.filter(or_number=or_number).exists():
                messages.error(request, f'OR Number "{or_number}" is already used by another certificate.')
                return redirect('certifications:issue')

        if cert_type == 'cedula':
            ctc_number = request.POST.get('ctc_number')
            if ctc_number:
                if Cedula.objects.filter(ctc_number=ctc_number).exists():
                    messages.error(request, f'CTC Number "{ctc_number}" is already used.')
                    return redirect('certifications:issue')

        def to_decimal(val):
            if not val: return Decimal('0.00')
            try:
                # Remove commas if any
                clean_val = str(val).replace(',', '')
                return Decimal(clean_val)
            except:
                return Decimal('0.00')

        control_number = request.POST.get('control_number')
        if not control_number:
            control_number = generate_control_number(cert_type)

        cert = Certificate(
            cert_type=cert_type,
            control_number=control_number,
            resident=resident,
            purpose=request.POST.get('purpose', ''),
            or_number=or_number or None, # Use None for blank to avoid unique "" conflict
            amount_paid=to_decimal(request.POST.get('amount_paid', 0)),
            business_name=request.POST.get('business_name', ''),
            business_address=request.POST.get('business_address', ''),
            business_type=request.POST.get('business_type', ''),
            issued_by=request.user,
            status='issued',
        )
        cert.save()

        if cert_type == 'cedula':
            # Create Cedula details
            cedula = Cedula.objects.create(
                certificate=cert,
                ctc_number=request.POST.get('ctc_number'),
                taxpayer_type=request.POST.get('taxpayer_type', 'individual'),
                place_of_issue=request.POST.get('place_of_issue', 'Sico-Sico, Gigaquit'),
                height=request.POST.get('height', ''),
                weight=request.POST.get('weight', ''),
                
                # Raw taxable amounts
                raw_taxable_property=to_decimal(request.POST.get('raw_taxable_property')),
                raw_taxable_business=to_decimal(request.POST.get('raw_taxable_business')),
                raw_taxable_income=to_decimal(request.POST.get('raw_taxable_income')),
                
                basic_tax=to_decimal(request.POST.get('basic_tax')),
                additional_tax_property=to_decimal(request.POST.get('additional_tax_property')),
                additional_tax_business=to_decimal(request.POST.get('additional_tax_business')),
                additional_tax_income=to_decimal(request.POST.get('additional_tax_income')),
                interest=to_decimal(request.POST.get('interest'))
            )
            # Cedula.save() is called by objects.create(), which updates certificate.amount_paid

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
    pdf_buffer = generate_certificate_pdf(cert)
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
        exists = Certificate.objects.filter(or_number=value).exists()
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
    """Delete a certificate (POST only)."""
    cert = get_object_or_404(Certificate, pk=pk)
    if request.method == 'POST':
        control_number = cert.control_number
        cert.delete()
        messages.success(request, f'Certificate {control_number} has been deleted.')
    return redirect('certifications:list')
