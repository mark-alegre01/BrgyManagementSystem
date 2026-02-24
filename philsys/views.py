from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.contrib.auth.decorators import login_required
import json

from .models import PhilSysVerificationAttempt
from residents.models import Resident
from core.models import UserProfile


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def verify_philsys(request):
    """Verify PhilSys credentials for a resident."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    resident_id = data.get("resident_id")
    philSys_number = data.get("philSys_number")
    philSys_card_number = data.get("philSys_card_number")
    verification_method = data.get("verification_method", "psn")

    if verification_method not in ["qr", "psn", "biometric"]:
        return JsonResponse({"error": "Invalid verification method"}, status=400)

    if not resident_id:
        return JsonResponse({"error": "Resident ID is required"}, status=400)

    try:
        resident = Resident.objects.get(id=resident_id)
    except Resident.DoesNotExist:
        return JsonResponse({"error": "Resident not found"}, status=404)

    attempt = PhilSysVerificationAttempt.objects.create(
        user=request.user,
        resident=resident,
        philSys_number=philSys_number,
        philSys_card_number=philSys_card_number,
        verification_method=verification_method,
        ip_address=get_client_ip(request),
    )

    attempt.status = "success"
    attempt.completed_at = timezone.now()
    attempt.response_data = {
        "verified": True,
        "philSys_number": philSys_number,
        "message": "PhilSys verification successful",
    }
    attempt.save()

    resident.is_philsys_verified = True
    resident.philsys_verified_at = timezone.now()
    resident.philsys_verification_method = verification_method
    if philSys_number:
        resident.philSys_number = philSys_number
    if philSys_card_number:
        resident.philSys_card_number = philSys_card_number
    resident.save()

    user_profile = UserProfile.objects.filter(user=request.user).first()
    if user_profile:
        user_profile.is_philsys_verified = True
        user_profile.philsys_verified_at = timezone.now()
        if philSys_number:
            user_profile.philSys_id = philSys_number
        user_profile.save()

    return JsonResponse(
        {
            "success": True,
            "verification_id": attempt.id,
            "message": "PhilSys verification successful",
        }
    )


@login_required
def verification_history(request):
    """Get verification history for the current user."""
    attempts = (
        PhilSysVerificationAttempt.objects.filter(user=request.user)
        .select_related("resident")
        .order_by("-created_at")[:50]
    )

    data = [
        {
            "id": attempt.id,
            "resident_name": str(attempt.resident) if attempt.resident else None,
            "philSys_number": attempt.philSys_number,
            "verification_method": attempt.verification_method,
            "status": attempt.status,
            "created_at": attempt.created_at.isoformat(),
            "completed_at": attempt.completed_at.isoformat()
            if attempt.completed_at
            else None,
        }
        for attempt in attempts
    ]

    return JsonResponse({"attempts": data})


@login_required
def check_verification(request, resident_id):
    """Check if a resident is PhilSys verified."""
    try:
        resident = Resident.objects.get(id=resident_id)
    except Resident.DoesNotExist:
        return JsonResponse({"error": "Resident not found"}, status=404)

    return JsonResponse(
        {
            "is_verified": resident.is_philsys_verified,
            "philSys_number": resident.philSys_number,
            "philsys_verified_at": resident.philsys_verified_at.isoformat()
            if resident.philsys_verified_at
            else None,
            "verification_method": resident.philsys_verification_method,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def verify_qr_code(request):
    """Verify PhilID QR code (simulated - validates QR structure)."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    qr_data = data.get("qr_data")
    resident_id = data.get("resident_id")

    if not qr_data:
        return JsonResponse({"error": "QR data is required"}, status=400)

    if not resident_id:
        return JsonResponse({"error": "Resident ID is required"}, status=400)

    try:
        resident = Resident.objects.get(id=resident_id)
    except Resident.DoesNotExist:
        return JsonResponse({"error": "Resident not found"}, status=404)

    attempt = PhilSysVerificationAttempt.objects.create(
        user=request.user,
        resident=resident,
        verification_method="qr",
        ip_address=get_client_ip(request),
    )

    if not qr_data.startswith("PHL-") or len(qr_data) < 10:
        attempt.status = "failed"
        attempt.error_message = (
            "Invalid QR code format. Expected format: PHL-XXXXXXXXXX"
        )
        attempt.save()
        return JsonResponse(
            {
                "success": False,
                "verification_id": attempt.id,
                "message": "Invalid QR code format",
            },
            status=400,
        )

    attempt.status = "success"
    attempt.completed_at = timezone.now()
    attempt.response_data = {
        "verified": True,
        "qr_data": qr_data[:8] + "****",
        "message": "QR code verification successful",
    }
    attempt.save()

    return JsonResponse(
        {
            "success": True,
            "verification_id": attempt.id,
            "message": "QR code verification successful",
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def verify_psn(request):
    """Verify via PhilSys Number (simulated)."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    philSys_number = data.get("philSys_number")
    resident_id = data.get("resident_id")

    if not philSys_number:
        return JsonResponse({"error": "PhilSys Number is required"}, status=400)

    if not resident_id:
        return JsonResponse({"error": "Resident ID is required"}, status=400)

    try:
        resident = Resident.objects.get(id=resident_id)
    except Resident.DoesNotExist:
        return JsonResponse({"error": "Resident not found"}, status=404)

    attempt = PhilSysVerificationAttempt.objects.create(
        user=request.user,
        resident=resident,
        philSys_number=philSys_number,
        verification_method="psn",
        ip_address=get_client_ip(request),
    )

    if not philSys_number.isdigit() or len(philSys_number) != 12:
        attempt.status = "failed"
        attempt.error_message = "Invalid PhilSys Number. Must be 12 digits."
        attempt.save()
        return JsonResponse(
            {
                "success": False,
                "verification_id": attempt.id,
                "message": "Invalid PhilSys Number format",
            },
            status=400,
        )

    attempt.status = "success"
    attempt.completed_at = timezone.now()
    attempt.response_data = {
        "verified": True,
        "philSys_number": philSys_number[:4] + "********",
        "message": "PhilSys Number verification successful",
    }
    attempt.save()

    return JsonResponse(
        {
            "success": True,
            "verification_id": attempt.id,
            "message": "PhilSys Number verification successful",
        }
    )


@login_required
def get_verification_status(request, attempt_id):
    """Get verification status by attempt ID."""
    try:
        attempt = PhilSysVerificationAttempt.objects.get(id=attempt_id)
    except PhilSysVerificationAttempt.DoesNotExist:
        return JsonResponse({"error": "Verification attempt not found"}, status=404)

    return JsonResponse(
        {
            "id": attempt.id,
            "verification_method": attempt.verification_method,
            "status": attempt.status,
            "philSys_number": attempt.philSys_number,
            "error_message": attempt.error_message,
            "created_at": attempt.created_at.isoformat(),
            "completed_at": attempt.completed_at.isoformat()
            if attempt.completed_at
            else None,
        }
    )


def get_client_ip(request):
    """Get client IP address from request."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip
