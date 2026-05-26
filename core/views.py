from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
User = get_user_model()
from django.http import JsonResponse, FileResponse
from django import forms
from django.utils.text import slugify
from django.utils.timezone import now
from django.core.cache import cache
import secrets
import os
import sys
import subprocess
from .models import UserProfile
from residents.models import Resident, Household, ResidentRegistration
from certifications.models import Certificate
from officials.models import Official
from attendance.models import AttendanceLog
from ordinances.models import Ordinance
from datetime import date
from .utils.backup import perform_backup, get_backup_destinations, create_backup_archive
from biometrics.utils import get_biometric_provider
from django.conf import settings
from django.db.models import Max
from core.utils.biometric_discovery import get_esp32_base_url
import requests


OFFICIAL_ROLE_CHOICES = [
    ('captain', 'Barangay Captain'),
    ('secretary', 'Secretary'),
    ('treasurer', 'Treasurer'),
    ('bhw', 'Barangay BHW'),
    ('resident', 'Resident'),
]

OFFICIAL_USERNAME_BY_ROLE = {
    'captain': 'captain',
    'secretary': 'secretary',
    'treasurer': 'treasurer',
    'bhw': 'bhw',
    'admin': 'admin',
}


MIN_FINGERPRINT_TEMPLATE_LEN = 10

# ESP32 passwordless login: only these positions may complete Django login via fingerprint.
BIOMETRIC_LOGIN_ALLOWED_POSITIONS = ('captain', 'secretary', 'treasurer')

ROLE_TEMPLATE_MAP = {
    'captain': 'core/dashboard_captain.html',
    'admin': 'core/dashboard_captain.html',
    'secretary': 'core/dashboard_secretary.html',
    'treasurer': 'core/dashboard_treasurer.html',
    'kagawad': 'core/dashboard_kagawad.html',
    'sk_chairman': 'core/dashboard_sk.html',
    'sk_chairperson': 'core/dashboard_sk.html',  # alias
    'lupon': 'core/dashboard_lupon.html',
    'lupong_member': 'core/dashboard_lupon.html',  # alias
    'bhw': 'core/dashboard_default.html',
    'tanod': 'core/dashboard_default.html',
    'staff': 'core/dashboard_default.html',
    'clerk': 'core/dashboard_default.html',
    'resident': 'core/dashboard_resident.html',
}


@login_required
def dashboard(request):
    """Role-based dashboard dispatcher."""
    # Consume biometric flags set by biometric_login_complete
    biometrically_verified = request.session.pop('biometrically_verified', False)
    biometric_position = request.session.pop('biometric_position', None)

    today = date.today()

    # Determine role:
    # Priority 1: role explicitly set during biometric login
    # Priority 2: active Official record linked to this user
    # Priority 3: UserProfile / User.role fallback
    role = 'resident'

    if biometric_position:
        # Trust the position recorded at biometric login time
        role = biometric_position
    else:
        # 1. Check if user has an active official position
        try:
            official = request.user.official_profile
            if official and official.status == 'active':
                role = official.position
        except Exception:
            pass

        if role == 'resident':
            # 2. Fallback to UserProfile / User.role
            try:
                profile_role = request.user.profile.role
                if profile_role:
                    role = profile_role
            except Exception:
                pass

    # Superuser always gets admin/captain view
    if request.user.is_superuser:
        role = 'admin'

    # Shared base context
    context = {
        'today': today,
        'total_residents': Resident.objects.filter(is_active=True).count(),
        'total_households': Household.objects.count(),
        'total_officials': Official.objects.filter(status='active').count(),
        'total_ordinances': Ordinance.objects.filter(status='active').count(),
        'certificates_today': Certificate.objects.filter(date_issued=today).count(),
        'certificates_total': Certificate.objects.count(),
        'attendance_today': AttendanceLog.objects.filter(date=today).count(),
        'pending_registrations_count': ResidentRegistration.objects.filter(status='pending').count(),
        'pending_registrations_today': ResidentRegistration.objects.filter(status='pending', created_at__date=today).count(),
        'recent_certificates': Certificate.objects.select_related('resident').order_by('-date_issued')[:5],
        'recent_residents': Resident.objects.order_by('-created_at')[:5],
        'male_count': Resident.objects.filter(gender='M', is_active=True).count(),
        'female_count': Resident.objects.filter(gender='F', is_active=True).count(),
    }

    # Role-specific extra context
    if role in ('captain', 'admin'):
        context['recent_officials'] = Official.objects.select_related('resident').order_by('-created_at')[:5]
        context['recent_ordinances'] = Ordinance.objects.order_by('-date_enacted')[:5]

    elif role == 'secretary':
        context['pending_certs'] = Certificate.objects.filter(date_issued=today).count()
        context['recent_ordinances'] = Ordinance.objects.order_by('-date_enacted')[:5]

    elif role == 'treasurer':
        context['attendance_logs'] = AttendanceLog.objects.select_related('official__resident').filter(date=today)[:10]

    elif role == 'kagawad':
        context['recent_ordinances'] = Ordinance.objects.order_by('-date_enacted')[:5]

    elif role == 'sk_chairperson':
        from django.utils.timezone import now
        from datetime import timedelta
        cutoff = date.today().replace(year=date.today().year - 30)
        context['youth_count'] = Resident.objects.filter(is_active=True, birthdate__gte=cutoff).count()

    elif role == 'lupong_member':
        context['recent_ordinances'] = Ordinance.objects.order_by('-date_enacted')[:5]

    elif role == 'resident':
        # Personalized resident portal context
        from certifications.models import Certificate as Cert
        try:
            resident_record = request.user.profile.resident
            context['resident_record'] = resident_record
            if resident_record:
                context['my_certificates'] = Cert.objects.filter(
                    resident=resident_record
                ).order_by('-date_issued')[:5]
            else:
                context['my_certificates'] = []
        except Exception:
            context['resident_record'] = None
            context['my_certificates'] = []
        context['cert_types'] = Cert.TYPE_CHOICES

    template = ROLE_TEMPLATE_MAP.get(role, 'core/dashboard_default.html')
    return render(request, template, context)


from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q
import json

@csrf_exempt
def biometric_templates(request):
    """API for the 32-bit service to fetch all registered templates."""
    role = (request.GET.get('role') or '').strip()
    username_param = (request.GET.get('username') or '').strip()
    profiles = UserProfile.objects.exclude(fingerprint_template__isnull=True).exclude(fingerprint_template='')
    
    if username_param:
        profiles = profiles.filter(user__username=username_param)
    elif role:
        username = OFFICIAL_USERNAME_BY_ROLE.get(role)
        if username:
            profiles = profiles.filter(user__username=username)
        else:
            profiles = profiles.filter(role=role)
    templates = []
    for p in profiles:
        if p.fingerprint_template and len(p.fingerprint_template) >= MIN_FINGERPRINT_TEMPLATE_LEN:
            templates.append({
                'id': p.user.id,
                'template': p.fingerprint_template
            })
    return JsonResponse({'templates': templates})

@csrf_exempt
@require_http_methods(["POST"])
def biometric_verify_login(request):
    """API for the 32-bit service to notify successful verification."""
    try:
        data = json.loads(request.body)
        user_id = data.get('user_id')
        request_id = data.get('request_id')
        if not request_id:
            return JsonResponse({'status': 'error', 'message': 'Missing request_id'}, status=400)

        expected = cache.get(f"biometric:{request_id}") or {}
        expected_role = (expected.get('role') or '').strip()

        user = User.objects.get(id=user_id)

        # Biometric login: allow classic long template OR R307 slot on linked resident
        profile = UserProfile.objects.filter(user=user).first()
        resident = profile.resident if profile else None
        tpl_ok = (
            profile
            and profile.fingerprint_template
            and len(profile.fingerprint_template) >= MIN_FINGERPRINT_TEMPLATE_LEN
        )
        sensor_ok = resident is not None and resident.fingerprint_id is not None
        if not profile or (not tpl_ok and not sensor_ok):
            if request_id:
                cache.set(
                    f"biometric:{request_id}",
                    {"status": "failed", "reason": "Fingerprint not registered"},
                    timeout=120,
                )
            return JsonResponse({'status': 'error', 'message': 'Fingerprint not registered'}, status=403)

        if expected_role:
            expected_username = OFFICIAL_USERNAME_BY_ROLE.get(expected_role)
            if expected_username and (user.username or '').strip() != expected_username:
                cache.set(
                    f"biometric:{request_id}",
                    {"status": "failed", "reason": "Role mismatch"},
                    timeout=120,
                )
                return JsonResponse({'status': 'error', 'message': 'Role mismatch'}, status=403)

            if (profile.role or '').strip() and (profile.role or '').strip() != expected_role:
                cache.set(
                    f"biometric:{request_id}",
                    {"status": "failed", "reason": "Role mismatch"},
                    timeout=120,
                )
                return JsonResponse({'status': 'error', 'message': 'Role mismatch'}, status=403)

        if expected_role and not OFFICIAL_USERNAME_BY_ROLE.get(expected_role) and (profile.role or '').strip() != expected_role:
            cache.set(
                f"biometric:{request_id}",
                {"status": "failed", "reason": "Role mismatch"},
                timeout=120,
            )
            return JsonResponse({'status': 'error', 'message': 'Role mismatch'}, status=403)

        cache.set(
            f"biometric:{request_id}",
            {"status": "authenticated", "user_id": user.id},
            timeout=120,
        )
        return JsonResponse({'status': 'success', 'message': f'Verified as {user.username}'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def biometric_verify_login_start(request):
    """View to initiate biometric verification."""
    try:
        request_id = secrets.token_urlsafe(16)
        request.session['biometric_request_id'] = request_id
        cache.set(f"biometric:{request_id}", {"status": "pending"}, timeout=120)
        
        # Use BiometricProvider interface
        provider = get_biometric_provider()
        result = provider.verify(user_id=request.user.id, scan_data={'request_id': request_id})
        
        return JsonResponse({
            'status': 'success', 
            'message': result.get('message', 'Verification service initiated'), 
            'request_id': request_id
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
def biometric_login_start(request):
    """Public view to initiate biometric verification for login."""
    try:
        role = ''
        if request.method == 'POST':
            try:
                payload = json.loads(request.body) if request.body else {}
            except json.JSONDecodeError:
                payload = {}
            role = (payload.get('role') or '').strip()
            username = (payload.get('username') or '').strip()
        role = role or (request.GET.get('role') or '').strip()
        username = username or (request.GET.get('username') or '').strip()

        if role and role != 'auto' and role not in dict(OFFICIAL_ROLE_CHOICES):
            return JsonResponse({'status': 'error', 'message': 'Invalid role'}, status=400)

        request_id = secrets.token_urlsafe(16)
        request.session['biometric_request_id'] = request_id
        
        _esp32_trigger_start_verification()

        cache.set(f"biometric:{request_id}", {"status": "pending", "role": role, "username": username}, timeout=120)
        
        return JsonResponse({
            'status': 'success', 
            'message': 'Biometric verification initiated. Please scan your finger.', 
            'request_id': request_id
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
def biometric_status_check(request):
    """Check if the biometric verification was successful by polling ESP32 status."""
    request_id = request.session.get('biometric_request_id')
    if not request_id:
        return JsonResponse({'status': 'none'})

    state = cache.get(f"biometric:{request_id}") or {"status": "pending"}
    
    if state.get('status') == 'failed':
        return JsonResponse({'status': 'failed', 'reason': state.get('reason')})
    
    if state.get('status') == 'authenticated':
        # Already authenticated in a previous poll
        return JsonResponse({'status': 'authenticated'})

    # Poll ESP32 for detection
    esp32_base_url = get_esp32_base_url()
    try:
        resp = requests.get(
            f"{esp32_base_url}/status",
            timeout=(3, 5),
            proxies={'http': None, 'https': None},
        )
    except Exception:
        esp32_base_url = get_esp32_base_url(force_scan=True)
        try:
            resp = requests.get(
                f"{esp32_base_url}/status",
                timeout=(3, 5),
                proxies={'http': None, 'https': None},
            )
        except Exception as e:
            print(f"[Biometric] Status poll failed after scan: {str(e)}")
            return JsonResponse({'status': 'pending'})
    try:
        if resp.ok:
            data = resp.json()
            
            # Only fail on fingerprint not found errors during verification mode
            esp32_state_raw = data.get('state', '')
            if esp32_state_raw == 'auth_failed':
                reason = data.get('last_error', 'Fingerprint not recognized.')
                if reason.startswith("Auth Failed: "):
                    reason = reason[len("Auth Failed: "):]
                cache.set(f"biometric:{request_id}", {"status": "failed", "reason": reason}, timeout=120)
                return JsonResponse({'status': 'failed', 'reason': reason})

            # Fingerprint matched only when state is 'detected' (verify success pulse) or standby after.
            # fingerprint_id is 0-based (page 0 is valid); ESP omits the key when no match pending.
            esp32_state = data.get('state', '')
            has_fp = 'fingerprint_id' in data
            matched_id = data.get('fingerprint_id') if has_fp else None

            # Fingerprint matched — only Captain, Secretary, Treasurer may use biometric *login*
            if esp32_state in ('detected', 'standby') and has_fp and matched_id is not None:
                from officials.models import Official as OfficialModel
                user = None

                # Only allow active officials with an authorised position
                try:
                    official_rec = OfficialModel.objects.select_related('resident', 'user').filter(
                        resident__fingerprint_id=matched_id,
                        resident__is_active=True,
                        status='active',
                        position__in=BIOMETRIC_LOGIN_ALLOWED_POSITIONS,
                        user__isnull=False
                    ).first()
                    if official_rec:
                        print(f"[Biometric] Matched ID {matched_id}: "
                              f"{official_rec.resident.full_name} ({official_rec.position})")
                        user = official_rec.user
                except Exception as e:
                    print(f"[Biometric] Official lookup failed: {e}")

                # If no authorised official was found, reject immediately
                if not user:
                    # Check if any resident/other official owns this fingerprint_id
                    # so we can give a meaningful error
                    unauthorized = Resident.objects.filter(
                        fingerprint_id=matched_id, is_active=True
                    ).exists()
                    reason = (
                        "Fingerprint is not authorised for biometric login. "
                        "Only the Barangay Captain, Secretary, and Treasurer may sign in with fingerprint."
                        if unauthorized
                        else "Fingerprint not registered for biometric login."
                    )
                    try:
                        requests.post(f"{esp32_base_url}/error-feedback", data={'reason': 'Not Registered'}, timeout=2,
                                      proxies={'http': None, 'https': None})
                    except Exception:
                        pass
                    cache.set(f"biometric:{request_id}", {"status": "failed", "reason": reason}, timeout=30)
                    return JsonResponse({'status': 'failed', 'reason': reason})

                # Store user_id in cache — biometric_login_complete will do the actual login()
                cache.set(f"biometric:{request_id}", {"status": "authenticated", "user_id": user.id}, timeout=60)

                # Stop ESP32 verification
                try:
                    requests.post(f"{esp32_base_url}/stop-enrollment", timeout=1,
                                  proxies={'http': None, 'https': None})
                except Exception:
                    pass

                return JsonResponse({'status': 'authenticated'})
            # Wrong finger / bad scan during verify — ESP stays in session (soft retry).
            # Surface a hint to the login page without ending the biometric poll.
            esp_st = (data.get('state') or '').strip()
            last_err = (data.get('last_error') or '').strip()
            low = last_err.lower()
            if esp_st in ('wait_remove', 'verifying') and (
                'not recognized' in low or 'poor scan' in low or 'remove finger' in low
            ):
                return JsonResponse({
                    'status': 'pending',
                    'hint': 'Fingerprint not recognized. Remove your finger from the sensor, then try again.',
                })
    except Exception as e:
        print(f"[Biometric] Status poll failed: {str(e)}")

    return JsonResponse({'status': 'pending'})


def _esp32_trigger_start_verification(mode=None):
    """POST /start-verification on the ESP32. Returns True if ESP32 acknowledged, False otherwise."""
    esp32_base_url = get_esp32_base_url()
    max_slot = (
        Resident.objects.filter(is_active=True, fingerprint_id__isnull=False)
        .aggregate(m=Max('fingerprint_id'))
        .get('m')
    )
    
    payload = {}
    if max_slot is not None:
        payload['max_page'] = str(int(max_slot))
    if mode:
        payload['mode'] = mode

    try:
        resp = requests.post(
            f"{esp32_base_url}/start-verification",
            data=payload if payload else None,
            timeout=3,
            proxies={'http': None, 'https': None},
        )
        print(f"[Biometric] ESP32 /start-verification response: {resp.status_code} {resp.text[:100]}")
        return resp.ok
    except Exception as e:
        print(f"[Biometric] Failed to trigger ESP32: {str(e)}. Scanning...")
        esp32_base_url = get_esp32_base_url(force_scan=True)
        try:
            resp = requests.post(
                f"{esp32_base_url}/start-verification",
                data=payload if payload else None,
                timeout=3,
                proxies={'http': None, 'https': None},
            )
            return resp.ok
        except Exception as retry_err:
            print(f"[Biometric] Failed to trigger ESP32 after scan: {str(retry_err)}")
            return False


@csrf_exempt
@login_required
def biometric_attendance_start(request):
    """
    Start ESP32 verification for clock in/out.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    mode = 'attendance'
    try:
        data = json.loads(request.body)
        if 'mode' in data and data['mode']:
            mode = data['mode']
    except Exception:
        pass

    request_id = secrets.token_urlsafe(16)
    request.session['biometric_attendance_request_id'] = request_id
    request.session.save()
    esp32_ok = _esp32_trigger_start_verification(mode=mode)
    cache.set(f"biometric_attendance:{request_id}", {'status': 'pending'}, timeout=120)
    print(f"[Biometric] attendance_start: request_id={request_id}, esp32_ok={esp32_ok}")
    return JsonResponse({
        'status': 'success',
        'message': 'Attendance fingerprint scan started.',
        'request_id': request_id,
        'esp32_connected': esp32_ok,
    })


@csrf_exempt
def biometric_attendance_status_check(request):
    """Poll ESP32 after biometric_attendance_start; accept any active official with a matching slot.
       Also handles global hardware button polls without a request_id.
    """
    request_id = request.session.get('biometric_attendance_request_id')
    
    if request_id:
        state = cache.get(f"biometric_attendance:{request_id}") or {'status': 'pending'}
        if state.get('status') == 'failed':
            return JsonResponse({'status': 'failed', 'reason': state.get('reason')})
        if state.get('status') == 'authenticated':
            return JsonResponse({'status': 'authenticated', 'attendance_mode': state.get('attendance_mode', 'none')})

    esp32_base_url = get_esp32_base_url()
    try:
        resp = requests.get(
            f"{esp32_base_url}/status",
            timeout=(3, 5),
            proxies={'http': None, 'https': None},
        )
    except Exception:
        esp32_base_url = get_esp32_base_url(force_scan=True)
        try:
            resp = requests.get(
                f"{esp32_base_url}/status",
                timeout=(3, 5),
                proxies={'http': None, 'https': None},
            )
        except Exception as e:
            print(f"[Biometric] Attendance status poll failed after scan: {str(e)}")
            return JsonResponse({'status': 'pending'})
    try:
        if resp.ok:
            data = resp.json()
            esp32_state_raw = data.get('state', '')
            last_error = (data.get('last_error') or '').lower()
            if esp32_state_raw == 'auth_failed':
                reason = data.get('last_error', 'Fingerprint not recognized.')
                if reason.startswith("Auth Failed: "):
                    reason = reason[len("Auth Failed: "):]
                cache.set(
                    f"biometric_attendance:{request_id}",
                    {'status': 'failed', 'reason': reason},
                    timeout=120,
                )
                return JsonResponse({'status': 'failed', 'reason': reason})

            esp32_state = data.get('state', '')
            has_fp = 'fingerprint_id' in data
            matched_id = data.get('fingerprint_id') if has_fp else None

            if esp32_state in ('detected', 'standby') and has_fp and matched_id is not None:
                from officials.models import Official as OfficialModel
                official_rec = OfficialModel.objects.select_related('resident', 'user').filter(
                    resident__fingerprint_id=matched_id,
                    resident__is_active=True,
                    status='active',
                ).first()
                if not official_rec:
                    if Resident.objects.filter(fingerprint_id=matched_id, is_active=True).exists():
                        reason = (
                            'This fingerprint is not linked to an active barangay functionary. '
                            'Personnel must be enrolled as an official before using attendance scan.'
                        )
                    else:
                        reason = 'Fingerprint not registered in this system.'
                    try:
                        requests.post(
                            f"{esp32_base_url}/error-feedback",
                            data={'reason': 'Not Registered'},
                            timeout=2,
                            proxies={'http': None, 'https': None},
                        )
                    except Exception:
                        pass
                    cache.set(
                        f"biometric_attendance:{request_id}",
                        {'status': 'failed', 'reason': reason},
                        timeout=30,
                    )
                    return JsonResponse({'status': 'failed', 'reason': reason})

                attendance_mode = data.get('attendance_mode') or 'none'

                # Hardware validation: Reject TIME OUT if no TIME IN is recorded for today
                if attendance_mode == 'out':
                    from datetime import date
                    today = date.today()
                    log = AttendanceLog.objects.filter(official=official_rec, date=today).first()
                    if not log or (not log.am_in and not log.pm_in):
                        reason = 'No Clock-In'
                        try:
                            requests.post(
                                f"{esp32_base_url}/error-feedback",
                                data={'reason': reason},
                                timeout=2,
                                proxies={'http': None, 'https': None},
                            )
                        except Exception:
                            pass
                        
                        target_req_id = request_id or 'global_hardware_scan'
                        cache.set(
                            f"biometric_attendance:{target_req_id}",
                            {
                                'status': 'failed',
                                'reason': f"Clock-Out Rejected: No Clock-In recorded today for {official_rec.resident.full_name}."
                            },
                            timeout=30,
                        )
                        return JsonResponse({
                            'status': 'failed',
                            'reason': f"Clock-Out Rejected: No Clock-In recorded today for {official_rec.resident.full_name}."
                        })

                if request_id:
                    cache.set(
                        f"biometric_attendance:{request_id}",
                        {
                            'status': 'authenticated',
                            'official_id': official_rec.id,
                            'user_id': official_rec.user_id,
                            'attendance_mode': attendance_mode,
                        },
                        timeout=60,
                    )
                else:
                    # Global poll hit
                    temp_request_id = 'global_hardware_scan'
                    request.session['biometric_attendance_request_id'] = temp_request_id
                    cache.set(
                        f"biometric_attendance:{temp_request_id}",
                        {
                            'status': 'authenticated',
                            'official_id': official_rec.id,
                            'user_id': official_rec.user_id,
                            'attendance_mode': attendance_mode,
                        },
                        timeout=60,
                    )
                try:
                    requests.post(
                        f"{esp32_base_url}/stop-enrollment",
                        timeout=1,
                        proxies={'http': None, 'https': None},
                    )
                except Exception:
                    pass
                return JsonResponse({
                    'status': 'authenticated',
                    'attendance_mode': data.get('attendance_mode') or 'none'
                })

            esp_st = (data.get('state') or '').strip()
            last_err = (data.get('last_error') or '').strip()
            low = last_err.lower()
            if esp_st in ('wait_remove', 'verifying') and (
                'not recognized' in low or 'poor scan' in low or 'remove finger' in low
            ):
                return JsonResponse({
                    'status': 'pending',
                    'esp32_state': esp_st,
                    'hint': 'Fingerprint not recognized. Remove your finger from the sensor, then try again.',
                })
            
            return JsonResponse({'status': 'pending', 'esp32_state': esp_st})
    except Exception as e:
        print(f"[Biometric] Attendance status poll failed: {str(e)}")

    return JsonResponse({'status': 'pending'})


@csrf_exempt
def biometric_login_complete(request):
    """
    Final redirect step for biometric login.
    Called by the frontend after receiving 'authenticated' from the polling endpoint.
    Performs the actual Django login() here (full HTTP request, not AJAX) so the
    session cookie is reliably set before the browser follows the redirect.
    Biometric login is restricted to Captain, Secretary, and Treasurer only.
    """
    request_id = request.session.get('biometric_request_id')
    if not request_id:
        messages.error(request, 'Biometric session expired. Please scan again.')
        return redirect('core:login')

    state = cache.get(f"biometric:{request_id}") or {}
    if state.get('status') != 'authenticated':
        messages.error(request, 'Biometric authentication not completed. Please try again.')
        return redirect('core:login')

    user_id = state.get('user_id')
    if not user_id:
        messages.error(request, 'No user matched. Please try again.')
        return redirect('core:login')

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User account not found.')
        return redirect('core:login')

    # Final role guard: confirm the matched user is an authorised official
    from officials.models import Official as OfficialModel
    official_rec = OfficialModel.objects.filter(
        user=user,
        status='active',
        position__in=BIOMETRIC_LOGIN_ALLOWED_POSITIONS,
    ).first()
    if not official_rec:
        cache.delete(f"biometric:{request_id}")
        messages.error(
            request,
            'Access denied. Biometric login is only available to the Barangay Captain, '
            'Secretary, and Treasurer.'
        )
        return redirect('core:login')

    # Perform the real Django login here (full HTTP request)
    if not hasattr(user, 'backend'):
        user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)
    request.session['biometrically_verified'] = True

    # Clean up the cache entry
    cache.delete(f"biometric:{request_id}")

    # Redirect directly to the role-specific dashboard
    position = official_rec.position  # 'captain', 'secretary', or 'treasurer'
    role_dashboard_map = {
        'captain': 'core:dashboard',
        'secretary': 'core:dashboard',
        'treasurer': 'core:dashboard',
    }
    # Set session flag so dashboard() picks the right role even before profile refresh
    request.session['biometric_position'] = position
    return redirect('core:dashboard')

@login_required
def biometric_reset_all(request):
    """Clear all fingerprint data from the database and sync with ESP32."""
    role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    if not (request.user.is_superuser or role in ['captain', 'secretary', 'treasurer', 'admin']):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
        
    # 1. Clear Django Database
    Resident.objects.all().update(fingerprint_id=None, fingerprint_template=None)
    
    # 2. Erase all templates on the R307 module (flash can take several seconds)
    esp32_base_url = get_esp32_base_url()
    esp32_status = "offline"
    resp = None
    try:
        resp = requests.post(
            f"{esp32_base_url}/empty-library",
            timeout=10,
            proxies={'http': None, 'https': None},
        )
    except Exception:
        esp32_base_url = get_esp32_base_url(force_scan=True)
        try:
            resp = requests.post(
                f"{esp32_base_url}/empty-library",
                timeout=10,
                proxies={'http': None, 'https': None},
            )
        except Exception:
            pass

    if resp and resp.ok:
        try:
            payload = resp.json()
            if payload.get('status') == 'success':
                esp32_status = "sensor cleared"
            else:
                esp32_status = f"sensor error: {payload.get('message', resp.text)[:120]}"
        except ValueError:
            esp32_status = "sensor cleared" if resp.status_code == 200 else f"HTTP {resp.status_code}"
    elif resp is not None:
        esp32_status = f"HTTP {resp.status_code}"

    messages.success(
        request,
        f"Database biometric fields cleared. Fingerprint module: {esp32_status}. "
        "You can register fingerprints again from the enrollment page.",
    )
    return redirect('officials:biometric_register')

def login_view(request):
    """User login."""
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        user_type = request.POST.get('user_type', 'official')
        role = request.POST.get('role') if user_type == 'official' else 'resident'
        password = request.POST.get('password')
        
        if user_type == 'resident':
            username = request.POST.get('username')
        else:
            username = request.POST.get('official_username')
            role = None # Role is no longer used for identification

        if not username:
             messages.error(request, 'Username is required.')
             return render(request, 'core/login.html')

        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            profile = getattr(user, 'profile', None)
            user_role_name = profile.role if profile else (user.role.name if user.role else 'resident')
            # Use official record as fallback check for role permission
            from officials.models import Official
            has_active_official_record = Official.objects.filter(user=user, status='active').exists()
            is_official_user = user.is_superuser or (user.role and user.role.permission_level < 3) or has_active_official_record

            # Enforce separation as requested by the user
            if user_type == 'resident' and is_official_user:
                messages.error(request, f'Account "{username}" is assigned as an Official ({user_role_name}). Please log in using the "Official" tab with your role.')
                return render(request, 'core/login.html')
            
            if user_type == 'official':
                if not is_official_user:
                    messages.error(request, f'Account "{username}" is a Resident account. Please log in using the "Resident" tab.')
                    return render(request, 'core/login.html')

            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, f'Invalid credentials for "{username}". Please check your username and password.')

    return render(request, 'core/login.html')


def signup_view(request):
    messages.info(request, 'Public registration for officials is disabled. Please contact the Captain for an invite.')
    return redirect('core:login')


def resident_signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        # Collect all fields from the multi-step form
        try:
            from django.contrib.auth.hashers import make_password
            
            # Manual extraction from POST to support dynamic steps without a complex Form class
            reg = ResidentRegistration(
                # Step 1
                first_name=request.POST.get('first_name', '').strip(),
                middle_name=request.POST.get('middle_name', '').strip(),
                last_name=request.POST.get('last_name', '').strip(),
                suffix=request.POST.get('suffix', '').strip(),
                birthdate=request.POST.get('birthdate'),
                birthplace=request.POST.get('birthplace', '').strip(),
                gender=request.POST.get('gender'),
                civil_status=request.POST.get('civil_status'),
                nationality=request.POST.get('citizenship', 'Filipino').strip(),
                religion=request.POST.get('religion', '').strip(),
                highest_education=request.POST.get('highest_education'),
                occupation=request.POST.get('occupation', '').strip(),
                
                # Step 2
                mobile_number=request.POST.get('mobile_number', '').strip(),
                email=request.POST.get('email', '').strip(),
                house_number=request.POST.get('house_number', '').strip(),
                street=request.POST.get('street', '').strip(),
                purok=request.POST.get('purok', '').strip(),
                barangay=request.POST.get('barangay', '').strip(),
                municipality=request.POST.get('municipality', '').strip(),
                city=request.POST.get('city', '').strip(),
                zip_code=request.POST.get('zip_code', '').strip(),
                years_of_residency=int(request.POST.get('years_of_residency', 0)),
                philSys_number=request.POST.get('philSys_number', '').strip() or None,
                
                # Step 3
                is_joining_household=(request.POST.get('household_action') == 'join'),
                household_number=request.POST.get('household_number', '').strip(),
                is_pwd=(request.POST.get('is_pwd') == 'on'),
                is_senior_citizen=(request.POST.get('is_senior_citizen') == 'on'),
                is_4ps_member=(request.POST.get('is_4ps_member') == 'on'),
                is_sole_parent=(request.POST.get('is_sole_parent') == 'on'),
                is_registered_voter=(request.POST.get('is_registered_voter') == 'on'),
                
                guardian_name=request.POST.get('guardian_name', '').strip(),
                guardian_relationship=request.POST.get('guardian_relationship', '').strip(),
                guardian_contact=request.POST.get('guardian_contact', '').strip(),
                guardian_id_number=request.POST.get('guardian_id_number', '').strip(),
                
                # Step 4
                username=request.POST.get('username', '').strip(),
                password=make_password(request.POST.get('password1')),
                data_privacy_consent=(request.POST.get('data_privacy_consent') == 'on'),
            )
            
            # File Uploads
            if request.FILES.get('photo'):
                reg.photo = request.FILES['photo']
            if request.FILES.get('id_card'):
                reg.id_card = request.FILES['id_card']
            if request.FILES.get('birth_certificate'):
                reg.birth_certificate = request.FILES['birth_certificate']
            if request.FILES.get('proof_of_residency'):
                reg.proof_of_residency = request.FILES['proof_of_residency']
                
            # Check for duplicate username
            if User.objects.filter(username=reg.username).exists() or ResidentRegistration.objects.filter(username=reg.username, status='pending').exists():
                heads = Resident.objects.filter(is_household_head=True, is_active=True).select_related('household')
                messages.error(request, 'Username is already taken or pending approval.')
                return render(request, 'core/resident_signup.html', {'heads_of_households': heads})

            # Delete any existing rejected/approved registrations to avoid UNIQUE constraint violation
            # (Approved registrations have already been converted to User/Resident records)
            ResidentRegistration.objects.filter(username=reg.username).exclude(status='pending').delete()

            reg.save()
            return redirect('registration_success', ref=reg.reference_number)
            
        except Exception as e:
            heads = Resident.objects.filter(is_household_head=True, is_active=True).select_related('household')
            messages.error(request, f'Registration failed: {str(e)}')
            return render(request, 'core/resident_signup.html', {'heads_of_households': heads})
            
    heads = Resident.objects.filter(is_household_head=True, is_active=True).select_related('household')
    return render(request, 'core/resident_signup.html', {'heads_of_households': heads})




def registration_success_view(request, ref):
    registration = get_object_or_404(ResidentRegistration, reference_number=ref)
    return render(request, 'core/registration_success.html', {'registration': registration})


@login_required
def logout_view(request):
    """User logout."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')


@login_required
def backup_download(request):
    """Trigger data backup as a browser download."""
    role = 'staff'
    try: role = request.user.profile.role
    except Exception: pass
    
    if not (request.user.is_superuser or role in ('admin', 'captain', 'secretary', 'treasurer')):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
    
    try:
        zip_path = create_backup_archive()
        response = FileResponse(open(zip_path, 'rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(zip_path)}"'
        return response
    except Exception as e:
        messages.error(request, f"Download failed: {str(e)}")
        return redirect('core:backup_setup')


@login_required
def backup_execute(request):
    """Trigger data backup to a server-side destination."""
    role = 'staff'
    try: role = request.user.profile.role
    except Exception: pass
    
    if not (request.user.is_superuser or role in ('admin', 'captain', 'secretary', 'treasurer')):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
    
    if request.method == 'POST':
        target_path = request.POST.get('target_path')
        success, message = perform_backup(target_base=target_path)
        if success:
            messages.success(request, f"Done! {message}")
        else:
            messages.error(request, message)
    
    return redirect('core:backup_setup')


@login_required
def backup_mount_drive(request):
    """Attempt to mount a removable drive via udisksctl."""
    role = 'staff'
    try: role = request.user.profile.role
    except Exception: pass
    
    if not (request.user.is_superuser or role in ('admin', 'captain', 'secretary', 'treasurer')):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
        
    device = request.POST.get('device')
    do_backup = request.POST.get('perform_backup') == 'true'
    
    if device:
        import subprocess
        try:
            # Attempt to mount
            subprocess.run(['udisksctl', 'mount', '-b', device], check=True, timeout=10)
            
            if do_backup:
                import time
                from core.utils.backup import get_backup_destinations, perform_backup
                
                new_mount = None
                # OS might take a second to settle the mount, so we retry a few times
                for attempt in range(3):
                    time.sleep(1.5) # Wait for OS
                    all_dests = get_backup_destinations()
                    new_mount = next((d['path'] for d in all_dests if d.get('device') == device and d.get('is_mounted')), None)
                    if new_mount: break
                
                if new_mount:
                    success, message = perform_backup(target_base=new_mount)
                    if success:
                        messages.success(request, f"Drive activated and {message}")
                    else:
                        messages.warning(request, f"Drive activated, but backup failed: {message}")
                else:
                    messages.success(request, f"Drive {device} activated successfully. Please click 'Save' below.")
            else:
                messages.success(request, f"Drive {device} activated successfully.")
                
        except subprocess.TimeoutExpired:
            messages.warning(request, "Mount command timed out. Your drive might be ready, please refresh.")
        except Exception as e:
            messages.error(request, f"Failed to activate drive: {str(e)}")
            
    return redirect('core:backup_setup')


from django.http import JsonResponse
from core.utils.backup import get_backup_destinations

@login_required
def backup_check_dests(request):
    """JSON endpoint for polling backup destinations."""
    return JsonResponse({'destinations': get_backup_destinations()})

@login_required
def backup_setup(request):
    """Show available backup destinations (GUI for choosing location)."""
    role = 'staff'
    try: role = request.user.profile.role
    except Exception: pass
    
    if not (request.user.is_superuser or role in ('admin', 'captain', 'secretary', 'treasurer')):
        messages.error(request, "Permission denied.")
        return redirect('core:dashboard')
        
    destinations = get_backup_destinations()
    return render(request, 'core/backup_choice.html', {'destinations': destinations})


# ─── Notifications ────────────────────────────────────────────────────────────

@login_required
def notifications_view(request):
    """Full notifications list for the current user."""
    from .models import Notification
    notifs = Notification.objects.filter(user=request.user).order_by('-created_at')
    # Mark all as read on page open
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return render(request, 'core/notifications.html', {'notifications': notifs})


@login_required
def mark_notification_read(request, pk):
    """Mark a single notification as read (AJAX or redirect)."""
    from .models import Notification
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()
    next_url = request.GET.get('next') or notif.link or '/'
    return redirect(next_url)
