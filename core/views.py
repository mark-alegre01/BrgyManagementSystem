from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from residents.models import Resident, Household
from certifications.models import Certificate
from officials.models import Official
from attendance.models import AttendanceLog
from ordinances.models import Ordinance
from datetime import date


ROLE_TEMPLATE_MAP = {
    'captain': 'core/dashboard_captain.html',
    'admin': 'core/dashboard_captain.html',
    'secretary': 'core/dashboard_secretary.html',
    'treasurer': 'core/dashboard_treasurer.html',
    'kagawad': 'core/dashboard_kagawad.html',
    'sk_chairperson': 'core/dashboard_sk.html',
    'lupong_member': 'core/dashboard_lupon.html',
    'staff': 'core/dashboard_default.html',
    'resident': 'core/dashboard_default.html',
}


@login_required
def dashboard(request):
    """Role-based dashboard dispatcher."""
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


def login_view(request):
    """User login."""
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
            return redirect('core:dashboard')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'core/login.html')


@login_required
def logout_view(request):
    """User logout."""
    logout(request)
    messages.info(request, 'You have been logged out.')
    return redirect('core:login')
