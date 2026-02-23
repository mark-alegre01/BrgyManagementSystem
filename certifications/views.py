from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, FileResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Certificate
from residents.models import Resident
from datetime import date
import uuid


def generate_control_number(cert_type):
    """Generate unique control number for certificate."""
    prefix_map = {
        'clearance': 'CLR',
        'residency': 'RES',
        'indigency': 'IND',
        'good_moral': 'GMC',
        'business_permit': 'BP',
        'comelec': 'COM',
        'cedula': 'CED',
        'late_registration': 'LR',
    }
    prefix = prefix_map.get(cert_type, 'CERT')
    today = date.today()
    count = Certificate.objects.filter(
        cert_type=cert_type,
        date_issued=today
    ).count() + 1
    return f"{prefix}-{today.strftime('%Y%m%d')}-{count:04d}"


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

        cert = Certificate(
            cert_type=cert_type,
            control_number=generate_control_number(cert_type),
            resident=resident,
            purpose=request.POST.get('purpose', ''),
            or_number=request.POST.get('or_number', ''),
            amount_paid=request.POST.get('amount_paid', 0) or 0,
            business_name=request.POST.get('business_name', ''),
            business_address=request.POST.get('business_address', ''),
            business_type=request.POST.get('business_type', ''),
            issued_by=request.user,
            status='issued',
        )
        cert.save()
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
