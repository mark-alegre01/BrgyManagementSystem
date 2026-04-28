from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
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
}


MIN_FINGERPRINT_TEMPLATE_LEN = 100


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
    'resident': 'core/dashboard_default.html',
}


@login_required
def dashboard(request):
    """Role-based dashboard dispatcher."""
    # Clear biometric flag on dashboard load if they just logged in
    # This can be used for attendance tracking
    biometrically_verified = request.session.pop('biometrically_verified', False)
    
    today = date.today()

    # Determine role
    role = 'admin' if request.user.is_superuser else 'staff'
    try:
        role = request.user.profile.role
    except Exception:
        pass

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
    """View to launch the biometric verification service."""
    try:
        request_id = secrets.token_urlsafe(16)
        request.session['biometric_request_id'] = request_id
        cache.set(f"biometric:{request_id}", {"status": "pending"}, timeout=120)
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Use current python executable instead of hardcoded venv32
        venv_python = sys.executable
        service_path = os.path.join(base_dir, 'core', 'zk_verify.py')
        
        popen_args = [
            venv_python,
            service_path,
            '--url', request.build_absolute_uri('/')[:-1],
            '--request-id', request_id,
        ]

        if os.name == 'nt':
            subprocess.Popen(popen_args, creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
        else:
            subprocess.Popen(popen_args)
        
        return JsonResponse({'status': 'success', 'message': 'Verification service launched', 'request_id': request_id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
def biometric_login_start(request):
    """Public view to launch the biometric verification service for login."""
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

        if role and role not in dict(OFFICIAL_ROLE_CHOICES):
            return JsonResponse({'status': 'error', 'message': 'Invalid role'}, status=400)

        request_id = secrets.token_urlsafe(16)
        request.session['biometric_request_id'] = request_id
        cache.set(f"biometric:{request_id}", {"status": "pending", "role": role}, timeout=120)
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Use current python executable instead of hardcoded venv32
        venv_python = sys.executable
        service_path = os.path.join(base_dir, 'core', 'zk_verify.py')
        
        popen_args = [
            venv_python,
            service_path,
            '--url', request.build_absolute_uri('/')[:-1],
            '--request-id', request_id,
        ]
        if role:
            popen_args += ['--role', role]
        if username:
            popen_args += ['--username', username]

        if os.name == 'nt':
            subprocess.Popen(popen_args, creationflags=getattr(subprocess, 'CREATE_NEW_CONSOLE', 0))
        else:
            subprocess.Popen(popen_args)
        
        return JsonResponse({'status': 'success', 'message': 'Verification service launched', 'request_id': request_id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
def biometric_status_check(request):
    """Check if the biometric verification was successful."""
    request_id = request.session.get('biometric_request_id')
    if request_id:
        state = cache.get(f"biometric:{request_id}") or {"status": "pending"}
        if state.get('status') == 'failed':
            return JsonResponse({'status': 'failed', 'reason': state.get('reason')})
        if state.get('status') == 'authenticated' and state.get('user_id'):
            user = User.objects.get(id=state['user_id'])
            login(request, user)
            
            # Clean up
            try:
                del request.session['biometric_request_id']
            except Exception:
                pass
            cache.delete(f"biometric:{request_id}")
            request.session['biometrically_verified'] = True
            return JsonResponse({'status': 'authenticated'})

        return JsonResponse({'status': state.get('status', 'pending')})

    return JsonResponse({'status': 'none'})

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
            username = OFFICIAL_USERNAME_BY_ROLE.get(role)

        user = authenticate(request, username=username, password=password) if username else None
        if user is not None:
            if user_type == 'official' and not user.is_superuser:
               # Double check role matches the user profile for official roles
               profile = getattr(user, 'profile', None)
               if profile and profile.role != role:
                   messages.error(request, 'Role mismatch for this account.')
                   return render(request, 'core/login.html')

            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid credentials or role.')

    return render(request, 'core/login.html')


def signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    class SignupForm(forms.Form):
        first_name = forms.CharField(max_length=150)
        middle_name = forms.CharField(max_length=150, required=False)
        last_name = forms.CharField(max_length=150)
        role = forms.ChoiceField(choices=OFFICIAL_ROLE_CHOICES)
        password1 = forms.CharField(widget=forms.PasswordInput)
        password2 = forms.CharField(widget=forms.PasswordInput)

        def clean(self):
            cleaned = super().clean()
            p1 = cleaned.get('password1')
            p2 = cleaned.get('password2')
            if p1 and p2 and p1 != p2:
                raise forms.ValidationError('Passwords do not match.')
            return cleaned

    def _role_to_username(role: str) -> str:
        return OFFICIAL_USERNAME_BY_ROLE.get(role, '')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            first_name = form.cleaned_data['first_name'].strip()
            middle_name = (form.cleaned_data.get('middle_name') or '').strip()
            last_name = form.cleaned_data['last_name'].strip()
            role = form.cleaned_data['role']
            password = form.cleaned_data['password1']

            username = _role_to_username(role)
            if not username:
                form.add_error('role', 'Invalid role selected.')
                return render(request, 'core/signup.html', {'form': form})
            if User.objects.filter(username=username).exists():
                form.add_error('role', 'An account for this role already exists.')
                return render(request, 'core/signup.html', {'form': form})

            user = User.objects.create_user(username=username, password=password)
            user.first_name = first_name
            user.last_name = last_name
            user.save(update_fields=['first_name', 'last_name'])

            profile, _created = UserProfile.objects.get_or_create(
                user=user,
                defaults={'role': role, 'middle_name': middle_name},
            )
            updates = []
            if profile.role != role:
                profile.role = role
                updates.append('role')
            if (profile.middle_name or '') != middle_name:
                profile.middle_name = middle_name
                updates.append('middle_name')
            if updates:
                profile.save(update_fields=updates)

            login(request, user)
            messages.success(request, 'Account created successfully.')
            return redirect('dashboard')
    else:
        form = SignupForm()
    return render(request, 'core/signup.html', {'form': form})


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
