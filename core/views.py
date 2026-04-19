from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.http import JsonResponse
from django import forms
from django.utils.text import slugify
from django.utils.timezone import now
from django.core.cache import cache
import secrets
import os
import subprocess
from .models import UserProfile
from residents.models import Resident, Household
from certifications.models import Certificate
from officials.models import Official
from attendance.models import AttendanceLog
from ordinances.models import Ordinance
from datetime import date


OFFICIAL_ROLE_CHOICES = [
    ('captain', 'Barangay Captain'),
    ('secretary', 'Secretary'),
    ('treasurer', 'Treasurer'),
    ('bhw', 'Barangay BHW'),
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
from django.contrib.auth import login
from django.db.models import Q
import json

@csrf_exempt
def biometric_templates(request):
    """API for the 32-bit service to fetch all registered templates."""
    role = (request.GET.get('role') or '').strip()
    profiles = UserProfile.objects.exclude(fingerprint_template__isnull=True).exclude(fingerprint_template='')
    if role:
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
    """View to launch the 32-bit verification service."""
    try:
        request_id = secrets.token_urlsafe(16)
        request.session['biometric_request_id'] = request_id
        cache.set(f"biometric:{request_id}", {"status": "pending"}, timeout=120)
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        venv_python = os.path.join(base_dir, 'venv32', 'Scripts', 'python.exe')
        service_path = os.path.join(base_dir, 'core', 'zk_verify.py')
        
        if not os.path.exists(venv_python):
            return JsonResponse({'status': 'error', 'message': '32-bit environment not found'}, status=500)

        subprocess.Popen([
            venv_python,
            service_path,
            '--url', request.build_absolute_uri('/')[:-1],
            '--request-id', request_id,
        ], creationflags=subprocess.CREATE_NEW_CONSOLE)
        
        return JsonResponse({'status': 'success', 'message': 'Verification service launched', 'request_id': request_id})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@csrf_exempt
def biometric_login_start(request):
    """Public view to launch the 32-bit verification service for login."""
    try:
        role = ''
        if request.method == 'POST':
            try:
                payload = json.loads(request.body) if request.body else {}
            except json.JSONDecodeError:
                payload = {}
            role = (payload.get('role') or '').strip()
        role = role or (request.GET.get('role') or '').strip()

        if role and role not in dict(OFFICIAL_ROLE_CHOICES):
            return JsonResponse({'status': 'error', 'message': 'Invalid role'}, status=400)

        request_id = secrets.token_urlsafe(16)
        request.session['biometric_request_id'] = request_id
        cache.set(f"biometric:{request_id}", {"status": "pending", "role": role}, timeout=120)
        
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        venv_python = os.path.join(base_dir, 'venv32', 'Scripts', 'python.exe')
        service_path = os.path.join(base_dir, 'core', 'zk_verify.py')
        
        if not os.path.exists(venv_python):
            return JsonResponse({'status': 'error', 'message': '32-bit environment not found'}, status=500)

        popen_args = [
            venv_python,
            service_path,
            '--url', request.build_absolute_uri('/')[:-1],
            '--request-id', request_id,
        ]
        if role:
            popen_args += ['--role', role]

        subprocess.Popen(popen_args, creationflags=subprocess.CREATE_NEW_CONSOLE)
        
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
        role = request.POST.get('role')
        password = request.POST.get('password')
        username = OFFICIAL_USERNAME_BY_ROLE.get(role)
        user = authenticate(request, username=username, password=password) if username else None
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Invalid role or password.')

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
    return render(request, 'core/signup.html', {'form': form})


def resident_signup_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    class ResidentSignupForm(forms.Form):
        first_name = forms.CharField(max_length=150)
        middle_name = forms.CharField(max_length=150, required=False)
        last_name = forms.CharField(max_length=150)
        username = forms.CharField(max_length=150)
        philsys_id = forms.CharField(max_length=50, required=False)
        password1 = forms.CharField(widget=forms.PasswordInput)
        password2 = forms.CharField(widget=forms.PasswordInput)

        def clean(self):
            cleaned = super().clean()
            p1 = cleaned.get('password1')
            p2 = cleaned.get('password2')
            if p1 and p2 and p1 != p2:
                raise forms.ValidationError('Passwords do not match.')
            
            uname = cleaned.get('username')
            if User.objects.filter(username=uname).exists():
                raise forms.ValidationError('Username is already taken.')
            
            return cleaned

    if request.method == 'POST':
        form = ResidentSignupForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username'].strip()
            password = form.cleaned_data['password1']
            first_name = form.cleaned_data['first_name'].strip()
            last_name = form.cleaned_data['last_name'].strip()
            middle_name = (form.cleaned_data.get('middle_name') or '').strip()
            philsys_id = (form.cleaned_data.get('philsys_id') or '').strip()

            user = User.objects.create_user(username=username, password=password)
            user.first_name = first_name
            user.last_name = last_name
            user.save()

            # Create profile and try to link to resident
            resident = Resident.objects.none()
            if philsys_id:
                resident = Resident.objects.filter(philSys_number=philsys_id).first()
            
            if not resident:
                # Try name match
                resident = Resident.objects.filter(
                    first_name__iexact=first_name,
                    last_name__iexact=last_name
                ).first()

            UserProfile.objects.create(
                user=user,
                role='resident',
                middle_name=middle_name,
                philSys_id=philsys_id,
                resident=resident
            )

            login(request, user)
            messages.success(request, 'Account created successfully! You can now book appointments.')
            return redirect('dashboard')
    else:
        form = ResidentSignupForm()

    return render(request, 'core/resident_signup.html', {'form': form})


@login_required
def logout_view(request):
    """User logout."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('login')
