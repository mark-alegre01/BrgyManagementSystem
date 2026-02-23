from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from residents.models import Resident
from certifications.models import Certificate
from officials.models import Official
from attendance.models import AttendanceLog
from ordinances.models import Ordinance
from datetime import date


@login_required
def dashboard(request):
    """Main dashboard with statistics."""
    today = date.today()
    context = {
        'total_residents': Resident.objects.filter(is_active=True).count(),
        'total_households': Resident.objects.values('household').distinct().count(),
        'total_officials': Official.objects.filter(status='active').count(),
        'total_ordinances': Ordinance.objects.filter(status='active').count(),
        'certificates_today': Certificate.objects.filter(date_issued=today).count(),
        'certificates_total': Certificate.objects.count(),
        'attendance_today': AttendanceLog.objects.filter(date=today).count(),
        'recent_certificates': Certificate.objects.select_related('resident')[:5],
        'recent_residents': Resident.objects.order_by('-created_at')[:5],
        'male_count': Resident.objects.filter(gender='M', is_active=True).count(),
        'female_count': Resident.objects.filter(gender='F', is_active=True).count(),
    }
    return render(request, 'core/dashboard.html', context)


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
