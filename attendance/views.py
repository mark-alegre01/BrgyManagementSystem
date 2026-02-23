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
