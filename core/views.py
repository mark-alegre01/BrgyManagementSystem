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


ROLE_TEMPLATE_MAP = {
    'captain': 'core/dashboard_captain.html',
    'admin': 'core/dashboard_captain.html',
    'secretary': 'core/dashboard_secretary.html',
    'treasurer': 'core/dashboard_treasurer.html',
    'kagawad': 'core/dashboard_kagawad.html',
    'sk_chairperson': 'core/dashboard_sk.html',
    'lupong_member': 'core/dashboard_lupon.html',
    'bhw': 'core/dashboard_default.html',
    'staff': 'core/dashboard_default.html',
    'resident': 'core/dashboard_resident.html',
}


@login_required
def dashboard(request):
    """Role-based dashboard dispatcher."""
    # Clear biometric flag on dashboard load if they just logged in
    # This can be used for attendance tracking
    biometrically_verified = request.session.pop('biometrically_verified', False)
    
    today = date.today()

    # Determine role (Prioritize active official position, then UserProfile role)
    role = 'resident'
    
    # 1. Check if user is an active official
    official = getattr(request.user, 'official_profile', None)
    if official and official.status == 'active':
        role = official.position
    else:
        # 2. Fallback to UserProfile role
        try:
            profile_role = request.user.profile.role
            if profile_role:
                role = profile_role
        except Exception:
            pass
            
    # 3. Superuser always gets admin/captain view
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

        # Only allow biometric login for users with a registered fingerprint template
        profile = UserProfile.objects.filter(user=user).first()
        if (
            not profile
            or not profile.fingerprint_template
            or len(profile.fingerprint_template) < MIN_FINGERPRINT_TEMPLATE_LEN
        ):
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
        
        # Trigger ESP32 verification mode
        esp32_base_url = getattr(settings, 'ESP32_BASE_URL', 'http://192.168.1.55').rstrip('/')
        try:
            requests.post(f"{esp32_base_url}/start-verification", timeout=5, proxies={'http': None, 'https': None})
        except Exception as e:
            print(f"[Biometric] Failed to trigger ESP32: {str(e)}")

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
    esp32_base_url = getattr(settings, 'ESP32_BASE_URL', 'http://192.168.1.55').rstrip('/')
    try:
        resp = requests.get(f"{esp32_base_url}/status", timeout=2, proxies={'http': None, 'https': None})
        if resp.ok:
            data = resp.json()
            
            # Only fail on fingerprint not found errors during verification mode
            esp32_state_raw = data.get('state', '')
            last_error = data.get('last_error', '').lower()
            if esp32_state_raw == 'auth_failed' and ('not found' in last_error or 'account not found' in last_error):
                reason = data.get('last_error', 'Fingerprint not recognized.')
                cache.set(f"biometric:{request_id}", {"status": "failed", "reason": reason}, timeout=120)
                return JsonResponse({'status': 'failed', 'reason': reason})

            # Fingerprint matched only when state is 'detected' (scan 3 complete during VERIFYING)
            esp32_state = data.get('state', '')
            matched_id = data.get('fingerprint_id', 0)
            
            if esp32_state in ('detected', 'standby') and matched_id and matched_id > 0:
                from officials.models import Official as OfficialModel
                user = None
                
                # 1. Try: Official whose Resident record has this fingerprint_id
                try:
                    official_rec = OfficialModel.objects.select_related('resident', 'user').filter(
                        resident__fingerprint_id=matched_id,
                        resident__is_active=True,
                        user__isnull=False
                    ).first()
                    if official_rec:
                        print(f"[Biometric] Found match for ID {matched_id}: {official_rec.resident.full_name} (Official)")
                        user = official_rec.user
                except Exception as e:
                    print(f"[Biometric] Official lookup failed: {e}")
                
                # 2. Fallback: Resident with a linked UserProfile
                if not user:
                    try:
                        resident = Resident.objects.filter(
                            fingerprint_id=matched_id, is_active=True
                        ).select_related('user_profile__user').first()
                        if resident and hasattr(resident, 'user_profile') and resident.user_profile and resident.user_profile.user:
                            print(f"[Biometric] Found match for ID {matched_id}: {resident.full_name} (Resident)")
                            user = resident.user_profile.user
                    except Exception as e:
                        print(f"[Biometric] Resident lookup failed: {e}")
                
                if not user:
                    try:
                        requests.post(f"{esp32_base_url}/error-feedback", timeout=2, proxies={'http': None, 'https': None})
                    except Exception:
                        pass
                    reason = "Fingerprint not registered to any account"
                    cache.set(f"biometric:{request_id}", {"status": "failed", "reason": reason}, timeout=30)
                    return JsonResponse({'status': 'failed', 'reason': reason})
                
                # Store user_id in cache — biometric_login_complete will do the actual login()
                cache.set(f"biometric:{request_id}", {"status": "authenticated", "user_id": user.id}, timeout=60)
                
                # Stop ESP32 verification
                try:
                    requests.post(f"{esp32_base_url}/stop-enrollment", timeout=1, proxies={'http': None, 'https': None})
                except Exception:
                    pass
                
                return JsonResponse({'status': 'authenticated'})
    except Exception as e:
        print(f"[Biometric] Status poll failed: {str(e)}")

    return JsonResponse({'status': 'pending'})


@csrf_exempt
def biometric_login_complete(request):
    """
    Final redirect step for biometric login.
    Called by the frontend after receiving 'authenticated' from the polling endpoint.
    Performs the actual Django login() here (full HTTP request, not AJAX) so the
    session cookie is reliably set before the browser follows the redirect.
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

    # Perform the real Django login here (full HTTP request)
    if not hasattr(user, 'backend'):
        user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)
    request.session['biometrically_verified'] = True

    # Clean up the cache entry
    cache.delete(f"biometric:{request_id}")

    return redirect('core:dashboard')

@login_required
def biometric_reset_all(request):
    """Clear all fingerprint data from the database and sync with ESP32."""
    role = getattr(request.user.profile, 'role', None) if hasattr(request.user, 'profile') else None
    if not (request.user.is_superuser or role in ['captain', 'secretary', 'treasurer', 'admin']):
        return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
        
    # 1. Clear Django Database
    Resident.objects.all().update(fingerprint_id=None, fingerprint_template=None)
    
    # 2. Notify ESP32 to empty its library (redundancy)
    esp32_base_url = getattr(settings, 'ESP32_BASE_URL', 'http://192.168.1.55').rstrip('/')
    esp32_status = "offline"
    try:
        resp = requests.post(f"{esp32_base_url}/empty-library", timeout=3, proxies={'http': None, 'https': None})
        if resp.ok:
            esp32_status = "synced"
    except Exception:
        pass
        
    messages.success(request, f"Biometric records cleared. ESP32 sync: {esp32_status}")
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
            is_official_user = user.is_superuser or (user.role and user.role.permission_level < 3)

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
