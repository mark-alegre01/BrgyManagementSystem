from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import HttpResponse, FileResponse
from .models import Payment, OfficialReceipt
from certifications.models import CertificateRequest, Certificate
from .utils import calculate_certificate_fee, generate_receipt_pdf
from decimal import Decimal

def is_secretary_or_higher(user):
    try:
        return user.is_superuser or (hasattr(user, 'profile') and user.profile.role in ['captain', 'secretary', 'treasurer', 'admin'])
    except:
        return False

@login_required
def payment_dashboard(request):
    """Secretary's dashboard for managing payments."""
    if not is_secretary_or_higher(request.user):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
    
    status_filter = request.GET.get('status', 'pending')
    method_filter = request.GET.get('method', '')
    
    payments = Payment.objects.all()
    
    if status_filter:
        payments = payments.filter(status=status_filter)
    if method_filter:
        payments = payments.filter(method=method_filter)
        
    return render(request, 'payments/dashboard.html', {
        'payments': payments,
        'status_filter': status_filter,
        'method_filter': method_filter
    })

@login_required
def mark_as_paid(request, payment_id):
    """Secretary marks a cash payment as paid and issues an OR."""
    if not is_secretary_or_higher(request.user):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
    
    payment = get_object_or_404(Payment, id=payment_id)
    
    if request.method == 'POST':
        or_number = request.POST.get('or_number')
        if not or_number:
            or_number = OfficialReceipt.generate_next_or_number()
            
        # Create Official Receipt
        receipt = OfficialReceipt.objects.create(
            or_number=or_number,
            resident=payment.certificate_request.resident,
            amount=payment.amount,
            particulars=payment.certificate_request.get_cert_type_display(),
            issued_by=request.user
        )
        
        # Update Payment
        payment.status = 'paid'
        payment.official_receipt = receipt
        payment.verified_by = request.user
        payment.paid_at = timezone.now()
        payment.save()
        
        messages.success(request, f"Payment marked as PAID. OR Number: {or_number}")
    
    return redirect('payments:dashboard')

@login_required
def confirm_gcash_payment(request, payment_id):
    """Secretary confirms a GCash payment proof."""
    if not is_secretary_or_higher(request.user):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
    
    payment = get_object_or_404(Payment, id=payment_id)
    
    if request.method == 'POST':
        gcash_ref = request.POST.get('gcash_ref_number')
        
        # Create Official Receipt
        receipt = OfficialReceipt.objects.create(
            or_number=OfficialReceipt.generate_next_or_number(),
            resident=payment.certificate_request.resident,
            amount=payment.amount,
            particulars=f"{payment.certificate_request.get_cert_type_display()} (GCash)",
            issued_by=request.user
        )
        
        # Update Payment
        payment.status = 'paid'
        payment.gcash_ref_number = gcash_ref
        payment.official_receipt = receipt
        payment.verified_by = request.user
        payment.paid_at = timezone.now()
        payment.save()
        
        messages.success(request, "GCash payment confirmed successfully.")
        
    return redirect('payments:dashboard')

@login_required
def waive_fee(request, payment_id):
    """Secretary manually waives a fee for a resident."""
    if not is_secretary_or_higher(request.user):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
    
    payment = get_object_or_404(Payment, id=payment_id)
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Manual Waiver')
        
        payment.status = 'waived'
        payment.method = 'waived'
        payment.waive_reason = reason
        payment.verified_by = request.user
        payment.paid_at = timezone.now()
        payment.save()
        
        messages.warning(request, f"Fee waived for {payment.certificate_request.resident.full_name}. Reason: {reason}")
        
    return redirect('payments:dashboard')

@login_required
def resident_choose_payment(request, request_id):
    """Resident selects their payment method for a certificate request."""
    cert_request = get_object_or_404(CertificateRequest, id=request_id)
    
    # Ensure this is the resident's own request
    if cert_request.resident != request.user.profile.resident:
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
        
    if request.method == 'POST':
        method = request.POST.get('method')
        
        # Calculate fee (pass cert_request for accurate Cedula computation)
        amount, is_waived = calculate_certificate_fee(cert_request.resident, cert_request.cert_type, cert_request)
        
        # Create or Get Payment
        payment = cert_request.payment
        if not payment:
            payment = Payment.objects.create(amount=amount)
            cert_request.payment = payment
            cert_request.save()
        else:
            # Always sync the amount in case admin rates changed
            payment.amount = amount
            payment.save()
        
        payment.method = method
        if is_waived:
            payment.status = 'waived'
            payment.method = 'waived'
            payment.paid_at = timezone.now()
        elif method == 'gcash':
            payment.status = 'pending'
            if request.FILES.get('proof'):
                payment.proof_screenshot = request.FILES['proof']
        else: # Cash
            payment.status = 'unpaid'
            
        payment.save()
        
        if is_waived:
            messages.success(request, "Your fee has been automatically waived. Your request is now ready for processing.")
        else:
            messages.success(request, f"Payment method '{payment.get_method_display()}' selected. Please proceed as instructed.")
            
        return redirect('certifications:my_requests')

    amount, is_waived = calculate_certificate_fee(cert_request.resident, cert_request.cert_type, cert_request)
    
    # Get the same rate the admin uses for this cert type
    from certifications.views import get_certificate_rate
    standard_rate = get_certificate_rate(cert_request.cert_type)
    
    return render(request, 'payments/select_payment.html', {
        'cert_request': cert_request,
        'amount': amount,
        'standard_rate': standard_rate,
        'is_waived': is_waived,
    })

@login_required
def download_receipt(request, payment_id):
    """Generates and serves the PDF receipt."""
    payment = get_object_or_404(Payment, id=payment_id)
    
    # Ensure they have permission (Secretary or the specific Resident)
    is_authorized = False
    if is_secretary_or_higher(request.user):
        is_authorized = True
    elif hasattr(request.user, 'profile') and request.user.profile.resident == payment.certificate_request.resident:
        is_authorized = True
        
    if not is_authorized or not payment.official_receipt:
        messages.error(request, "Unauthorized or no receipt available.")
        return redirect('core:dashboard')
        
    pdf_buffer = generate_receipt_pdf(payment)
    return FileResponse(pdf_buffer, as_attachment=True, filename=f"Receipt_{payment.official_receipt.or_number}.pdf")
