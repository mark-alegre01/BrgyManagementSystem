from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from datetime import date, datetime, time
from .models import AttendanceLog, FaceEncoding
from officials.models import Official
import json
from biometrics.utils import get_biometric_provider


@login_required
def attendance_dashboard(request):
    """Attendance overview."""
    today = date.today()
    today_logs = AttendanceLog.objects.filter(date=today).select_related('official__resident')
    officials = Official.objects.filter(status='active')

    present_ids = set(today_logs.values_list('official_id', flat=True))
    absent_officials = officials.exclude(id__in=present_ids)

    context = {
        'today_logs': today_logs,
        'total_officials': officials.count(),
        'present_count': today_logs.filter(status__in=['present', 'late']).count(),
        'late_count': today_logs.filter(status='late').count(),
        'absent_count': absent_officials.count(),
        'absent_officials': absent_officials,
    }
    return render(request, 'attendance/dashboard.html', context)


@login_required
def clock_in_out(request):
    """Manual clock in/out page."""
    today = date.today()

    if request.method == 'POST':
        official_id = request.POST.get('official')
        action = request.POST.get('action')  # 'in' or 'out'
        official = get_object_or_404(Official, pk=official_id)

        log, created = AttendanceLog.objects.get_or_create(
            official=official,
            date=today,
            defaults={'method': 'manual', 'status': 'present'}
        )

        now = datetime.now().time()
        if action == 'in':
            log.time_in = now
            # Check if late (after 8:00 AM)
            if now > time(8, 0):
                log.status = 'late'
            else:
                log.status = 'present'
            log.save()
            messages.success(request, f'{official.resident.full_name} clocked IN at {now.strftime("%I:%M %p")}')
        elif action == 'out':
            log.time_out = now
            log.save()
            messages.success(request, f'{official.resident.full_name} clocked OUT at {now.strftime("%I:%M %p")}')

        return redirect('attendance:clock')

    officials = Official.objects.filter(status='active').select_related('resident')
    today_logs = {log.official_id: log for log in AttendanceLog.objects.filter(date=today)}

    context = {
        'officials': officials,
        'today_logs': today_logs,
        'current_time': datetime.now(),
    }
    return render(request, 'attendance/clock.html', context)


@login_required
def face_enroll(request):
    """Enroll face for an official."""
    if request.method == 'POST':
        official_id = request.POST.get('official')
        official = get_object_or_404(Official, pk=official_id)

        if request.FILES.get('photo'):
            face_enc, created = FaceEncoding.objects.get_or_create(official=official)
            face_enc.photo = request.FILES['photo']
            # In production, face encoding would be computed here
            face_enc.encoding_data = '[]'
            face_enc.save()
            messages.success(request, f'Face enrolled for {official.resident.full_name}')
        else:
            messages.error(request, 'Please upload a photo.')

        return redirect('attendance:enroll')

    officials = Official.objects.filter(status='active').select_related('resident')
    enrolled = set(FaceEncoding.objects.values_list('official_id', flat=True))

    context = {
        'officials': officials,
        'enrolled': enrolled,
    }
    return render(request, 'attendance/enroll.html', context)


@login_required
def dtr_list(request):
    """DTR summary for all officials."""
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)

    officials = Official.objects.filter(status='active').select_related('resident')

    dtr_summary = []
    for official in officials:
        logs = AttendanceLog.objects.filter(
            official=official,
            date__month=month,
            date__year=year,
        )
        total_hours = sum(log.hours_worked for log in logs)
        dtr_summary.append({
            'official': official,
            'present': logs.filter(status='present').count(),
            'late': logs.filter(status='late').count(),
            'absent': logs.filter(status='absent').count(),
            'total_hours': round(total_hours, 2),
            'total_days': logs.count(),
        })

    context = {
        'dtr_summary': dtr_summary,
        'month': int(month),
        'year': int(year),
    }
    return render(request, 'attendance/dtr.html', context)


@login_required
def dtr_detail(request, official_id):
    """Detailed DTR for a specific official."""
    official = get_object_or_404(Official, pk=official_id)
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)

    logs = AttendanceLog.objects.filter(
        official=official,
        date__month=month,
        date__year=year,
    ).order_by('date')

    total_hours = sum(log.hours_worked for log in logs)

    context = {
        'official': official,
        'logs': logs,
        'month': int(month),
        'year': int(year),
        'total_hours': round(total_hours, 2),
    }
    return render(request, 'attendance/dtr_detail.html', context)


@login_required
def dtr_print(request, official_id):
    """Print-friendly DTR."""
    official = get_object_or_404(Official, pk=official_id)
    month = request.GET.get('month', date.today().month)
    year = request.GET.get('year', date.today().year)

    logs = AttendanceLog.objects.filter(
        official=official,
        date__month=month,
        date__year=year,
    ).order_by('date')

    total_hours = sum(log.hours_worked for log in logs)

    context = {
        'official': official,
        'logs': logs,
        'month': int(month),
        'year': int(year),
        'total_hours': round(total_hours, 2),
    }
    return render(request, 'attendance/dtr_print.html', context)


def public_dtr_scan(request):
    """Public DTR page for functionaries to scan fingerprints without logging in."""
    return render(request, 'attendance/public_scan.html')


import requests

def match_1_to_n(target_template, target_type='official'):
    """
    Perform 1:N biometric matching using the configured provider.
    """
    if not target_template:
        return None

    provider = get_biometric_provider()
    # Note: In this architecture, we pass the template to the provider's verify method.
    # The provider decides how to match it against candidates.
    
    if target_type == 'official':
        candidates = Official.objects.exclude(fingerprint_template__isnull=True).exclude(fingerprint_template='')
        for cand in candidates:
            # We use the provider to verify the scan data against each candidate's stored template
            result = provider.verify(user_id=cand.id, scan_data={'template': target_template, 'stored_template': cand.fingerprint_template})
            if result.get('status') == 'success':
                return cand
    return None

@csrf_exempt
def api_biometric_verify(request):
    """
    API endpoint for biometric verification (Clock In/Out).
    Used by the 32-bit service or a public DTR kiosk.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        template = data.get('template')
        official_id = data.get('official_id')
        is_auto = data.get('auto', False)
        
        official = None
        if is_auto and request.user.is_authenticated:
            # Get the official profile for the logged in user
            official = getattr(request.user, 'official_profile', None)
        elif official_id:
            official = Official.objects.filter(pk=official_id).first()
        elif template:
            official = match_1_to_n(template)

        if not official:
            return JsonResponse({'status': 'failed', 'message': 'Fingerprint not recognized or session expired'})

        # Record attendance
        today = date.today()
        now = datetime.now().time()
        
        # Determine if Clock In or Clock Out
        requested_action = data.get('action') # 'in' or 'out'
        
        # Simple logic: if already clocked in today without clock out, then clock out.
        log = AttendanceLog.objects.filter(official=official, date=today).first()
        
        if requested_action == 'in' or (not requested_action and not log):
            # Clock In
            status = 'present'
            if now > time(8, 0): # Assuming 8 AM start
                status = 'late'
            
            if not log:
                log = AttendanceLog.objects.create(
                    official=official,
                    date=today,
                    time_in=now,
                    method='biometric',
                    status=status
                )
            else:
                log.time_in = now
                log.status = status
                log.save()
            action = 'Clocked IN'
        elif requested_action == 'out' or (not requested_action and log and not log.time_out):
            # Clock Out
            if not log:
                log = AttendanceLog.objects.create(
                    official=official,
                    date=today,
                    time_out=now,
                    method='biometric',
                    status='absent' # Should not happen usually
                )
            else:
                log.time_out = now
                log.save()
            action = 'Clocked OUT'
        else:
            return JsonResponse({'status': 'info', 'message': f'{official.resident.full_name} already completed DTR for today.'})

        return JsonResponse({
            'status': 'success',
            'message': f'{action} successful',
            'name': official.resident.full_name,
            'time': now.strftime("%I:%M %p"),
            'action': action
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def api_face_recognize(request):
    """API endpoint for Orange Pi face recognition.
    Accepts a photo via POST, returns recognized official or error.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    photo = request.FILES.get('photo')
    if not photo:
        return JsonResponse({'error': 'No photo provided'}, status=400)

    # In production, this would:
    # 1. Load the uploaded photo
    # 2. Extract face encoding
    # 3. Compare against stored encodings
    # 4. Return matched official info
    # For now, return a placeholder response

    return JsonResponse({
        'status': 'success',
        'message': 'Face recognition API endpoint ready. Connect face_recognition library for production use.',
        'recognized': False,
    })


@login_required
def biometric_attendance(request):
    """Page for officials to record attendance via biometric."""
    return render(request, 'attendance/biometric_attendance.html')
