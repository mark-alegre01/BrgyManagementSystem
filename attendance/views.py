from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.core.cache import cache
from datetime import date, datetime, time, timedelta
from django.utils import timezone
from .models import AttendanceLog, FaceEncoding, ShiftConfiguration, SpecialDate
from officials.models import Official
import json
from biometrics.utils import get_biometric_provider
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


@login_required
def attendance_dashboard(request):
    """Attendance overview."""
    today = timezone.localdate()
    today_logs = AttendanceLog.objects.filter(date=today).select_related('official__resident')
    officials = Official.objects.filter(status='active')

    # Get shift config for threshold
    day_names = {0:'mon', 1:'tue', 2:'wed', 3:'thu', 4:'fri', 5:'sat', 6:'sun'}
    day_code = day_names[today.weekday()]
    shift_config = ShiftConfiguration.objects.filter(day=day_code).first()

    log_dict = {log.official_id: log for log in today_logs}
    combined_logs = []
    
    for official in officials:
        log = log_dict.get(official.id)
        if log:
            combined_logs.append({
                'official': official,
                'date': log.date,
                'am_in': log.am_in,
                'am_out': log.am_out,
                'pm_in': log.pm_in,
                'pm_out': log.pm_out,
                'status': log.status,
                'has_log': True
            })
        else:
            combined_logs.append({
                'official': official,
                'date': today,
                'am_in': None,
                'am_out': None,
                'pm_in': None,
                'pm_out': None,
                'status': 'absent',
                'has_log': False
            })

    # Sort combined logs: Present first, then Late, then Absent
    status_order = {'present': 0, 'late': 1, 'absent': 2}
    combined_logs.sort(key=lambda x: (status_order.get(x['status'], 3), x['official'].resident.last_name))

    context = {
        'today_logs': combined_logs,
        'total_officials': officials.count(),
        'present_count': today_logs.filter(status__in=['present', 'late']).count(),
        'late_count': today_logs.filter(status='late').count(),
        'absent_count': officials.count() - today_logs.filter(status__in=['present', 'late']).count(),
        'shift_config': shift_config
    }
    return render(request, 'attendance/dashboard.html', context)


@login_required
def clock_in_out(request):
    """Manual clock in/out page."""
    today = timezone.localdate()

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
        
        # Get shift config for threshold
        day_names = {0:'mon', 1:'tue', 2:'wed', 3:'thu', 4:'fri', 5:'sat', 6:'sun'}
        day_code = day_names[today.weekday()]
        shift = ShiftConfiguration.objects.filter(day=day_code).first()

        if action == 'in':
            if not log.am_in:
                log.am_in = now
                action_label = "Morning Clock IN"
                # Check lateness
                threshold = shift.am_in if shift else time(8, 0)
                grace = shift.grace_period if shift else 15
                threshold_dt = datetime.combine(today, threshold) + timedelta(minutes=grace)
                if datetime.now() > threshold_dt:
                    log.status = 'late'
                else:
                    log.status = 'present'
            elif not log.pm_in:
                log.pm_in = now
                action_label = "Afternoon Clock IN"
            else:
                messages.warning(request, f'{official.resident.full_name} has already clocked IN for both shifts.')
                return redirect('attendance:clock')
            
            log.save()
            messages.success(request, f'{official.resident.full_name} {action_label} at {now.strftime("%I:%M %p")}')
        elif action == 'out':
            if not log.am_out:
                log.am_out = now
                action_label = "Morning Clock OUT"
            elif not log.pm_out:
                log.pm_out = now
                action_label = "Afternoon Clock OUT"
            else:
                # Allow updating PM OUT
                log.pm_out = now
                action_label = "Afternoon Clock OUT (Updated)"
                
            log.save()
            messages.success(request, f'{official.resident.full_name} {action_label} at {now.strftime("%I:%M %p")}')

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
    ).order_by('-date')

    total_hours = sum(log.hours_worked for log in logs)

    # Get all shift configs for lookup
    shifts = ShiftConfiguration.objects.all()
    shift_map = {s.day: s for s in shifts}
    day_names = {0:'mon', 1:'tue', 2:'wed', 3:'thu', 4:'fri', 5:'sat', 6:'sun'}
    
    # Enrich logs with their specific shift times for the template
    for log in logs:
        d_code = day_names[log.date.weekday()]
        s_cfg = shift_map.get(d_code)
        if s_cfg:
            log.shift_am_in = s_cfg.am_in
            log.shift_am_out = s_cfg.am_out
            log.shift_pm_in = s_cfg.pm_in
            log.shift_pm_out = s_cfg.pm_out
            log.grace_period = s_cfg.grace_period

    import calendar
    context = {
        'official': official,
        'logs': logs,
        'month': int(month),
        'month_name': calendar.month_name[int(month)],
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

    import calendar
    context = {
        'official': official,
        'logs': logs,
        'month': int(month),
        'month_name': calendar.month_name[int(month)],
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
    
    if target_type == 'official':
        candidates = Official.objects.exclude(fingerprint_template__isnull=True).exclude(fingerprint_template='')
        for cand in candidates:
            result = provider.verify(user_id=cand.id, scan_data={'template': target_template, 'stored_template': cand.fingerprint_template})
            if result.get('status') == 'success':
                return cand
    return None

@csrf_exempt
def api_biometric_verify(request):
    """
    API endpoint for biometric verification (Clock In/Out).
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    try:
        data = json.loads(request.body)
        template = data.get('template')
        official_id = data.get('official_id')
        is_auto = data.get('auto', False)
        
        official = None
        if is_auto:
            att_rid = request.session.get('biometric_attendance_request_id')
            if att_rid:
                att_state = cache.get(f"biometric_attendance:{att_rid}")
                if att_state and att_state.get('status') == 'authenticated':
                    oid = att_state.get('official_id')
                    if oid:
                        official = Official.objects.filter(pk=oid, status='active').first()

            if not official:
                request_id = request.session.get('biometric_request_id')
                if request_id:
                    state = cache.get(f"biometric:{request_id}")
                    if state and state.get('status') == 'authenticated':
                        matched_user_id = state.get('user_id')
                        if matched_user_id:
                            from django.contrib.auth import get_user_model
                            User = get_user_model()
                            try:
                                user = User.objects.get(id=matched_user_id)
                                official = getattr(user, 'official_profile', None)
                            except User.DoesNotExist:
                                pass

            if not official and request.user.is_authenticated:
                official = getattr(request.user, 'official_profile', None)
        elif official_id:
            official = Official.objects.filter(pk=official_id).first()
        elif template:
            official = match_1_to_n(template)

        if not official:
            return JsonResponse({'status': 'failed', 'message': 'Fingerprint not recognized or session expired'})

        device_time_str = data.get('device_time')
        device_date_str = data.get('device_date')
        
        is_auto = data.get('auto', False)
        if is_auto and (not device_time_str or not device_date_str):
            att_rid = request.session.get('biometric_attendance_request_id') or 'global_hardware_scan'
            if att_rid:
                att_state = cache.get(f"biometric_attendance:{att_rid}")
                if att_state:
                    device_time_str = device_time_str or att_state.get('device_time')
                    device_date_str = device_date_str or att_state.get('device_date')

        today = timezone.localdate()
        now = timezone.localtime().time()
        
        if device_time_str and device_date_str:
            try:
                parsed_dt = datetime.strptime(f"{device_date_str} {device_time_str}", "%Y-%m-%d %H:%M:%S")
                if parsed_dt.year >= 2026:
                    today = parsed_dt.date()
                    now = parsed_dt.time()
            except Exception as e:
                print(f"[Biometric] Failed to parse device date/time: {e}")

        requested_action = data.get('action')
        if requested_action == 'attendance' or not requested_action:
            requested_action = None

        log = AttendanceLog.objects.filter(official=official, date=today).first()
        
        # Get shift configuration for today
        day_names = {0:'mon', 1:'tue', 2:'wed', 3:'thu', 4:'fri', 5:'sat', 6:'sun'}
        day_code = day_names[today.weekday()]
        shift = ShiftConfiguration.objects.filter(day=day_code).first()
        
        if shift and shift.is_day_off:
            return JsonResponse({'status': 'info', 'message': f'Today is a Day Off for {official.resident.full_name}.'})

        # Determine slot based on time and requested action
        midpoint = time(12, 30) # Default midpoint
        if shift:
            # mid-point between AM OUT and PM IN
            h1, m1 = shift.am_out.hour, shift.am_out.minute
            h2, m2 = shift.pm_in.hour, shift.pm_in.minute
            mid_total_mins = ((h1 * 60 + m1) + (h2 * 60 + m2)) // 2
            midpoint = time(mid_total_mins // 60, mid_total_mins % 60)

        is_morning = now < midpoint
        action_label = ""
        
        from core.utils.biometric_discovery import get_esp32_base_url
        esp32_base_url = get_esp32_base_url()

        if not log:
            log = AttendanceLog.objects.create(official=official, date=today, method='biometric')

        target_field = None
        error_msg = ""
        
        # Determine target action and field based on time and requested action
        if requested_action == 'in':
            if is_morning:
                target_field = 'am_in'
                action_label = "Morning Clock IN"
                error_msg = "Morning IN already recorded."
            else:
                target_field = 'pm_in'
                action_label = "Afternoon Clock IN"
                error_msg = "Afternoon IN already recorded."
        elif requested_action == 'out':
            if is_morning:
                target_field = 'am_out'
                action_label = "Morning Clock OUT"
                error_msg = "Morning OUT already recorded."
            else:
                target_field = 'pm_out'
                action_label = "Afternoon Clock OUT"
                error_msg = "Afternoon OUT already recorded."
        else:
            # Auto-detect (requested_action is None or 'attendance')
            if is_morning:
                if not log.am_in:
                    target_field = 'am_in'
                    action_label = "Morning Clock IN"
                elif not log.am_out:
                    target_field = 'am_out'
                    action_label = "Morning Clock OUT"
                else:
                    # Clear state
                    if data.get('auto'):
                        att_rid = request.session.get('biometric_attendance_request_id')
                        if att_rid: cache.delete(f"biometric_attendance:{att_rid}")
                    try:
                        requests.post(f"{esp32_base_url}/error-feedback", data={'reason': 'Already Timed Out'}, timeout=2, proxies={'http': None, 'https': None})
                    except Exception:
                        pass
                    return JsonResponse({'status': 'failed', 'message': 'Morning shift already completed.'})
            else:
                # Afternoon
                if not log.pm_in:
                    target_field = 'pm_in'
                    action_label = "Afternoon Clock IN"
                elif not log.pm_out:
                    target_field = 'pm_out'
                    action_label = "Afternoon Clock OUT"
                else:
                    # Clear state
                    if data.get('auto'):
                        att_rid = request.session.get('biometric_attendance_request_id')
                        if att_rid: cache.delete(f"biometric_attendance:{att_rid}")
                    try:
                        requests.post(f"{esp32_base_url}/error-feedback", data={'reason': 'Already Timed Out'}, timeout=2, proxies={'http': None, 'https': None})
                    except Exception:
                        pass
                    return JsonResponse({'status': 'failed', 'message': 'Afternoon shift already completed.'})

        # Check if already recorded
        if getattr(log, target_field) is not None:
            if data.get('auto'):
                att_rid = request.session.get('biometric_attendance_request_id')
                if att_rid: cache.delete(f"biometric_attendance:{att_rid}")
            try:
                reason_err = 'Already Timed In' if 'IN' in action_label else 'Already Timed Out'
                requests.post(f"{esp32_base_url}/error-feedback", data={'reason': reason_err}, timeout=2, proxies={'http': None, 'https': None})
            except Exception:
                pass
            return JsonResponse({'status': 'failed', 'message': error_msg or f"{action_label} already recorded."})

        # Save the time
        setattr(log, target_field, now)

        # Handle lateness / status calculation for clock in
        local_now = timezone.localtime().replace(tzinfo=None)
        if target_field == 'am_in':
            threshold = shift.am_in if shift else time(8, 0)
            grace = shift.grace_period if shift else 15
            threshold_dt = datetime.combine(today, threshold) + timedelta(minutes=grace)
            log.status = 'late' if local_now > threshold_dt else 'present'
        elif target_field == 'pm_in':
            threshold = shift.pm_in if shift else time(13, 0)
            grace = shift.grace_period if shift else 15
            threshold_dt = datetime.combine(today, threshold) + timedelta(minutes=grace)
            if local_now > threshold_dt and log.status != 'late':
                log.status = 'late'

        log.save()

        # Clear active scan state
        is_auto = data.get('auto', False)
        if is_auto:
            att_rid = request.session.get('biometric_attendance_request_id')
            if att_rid:
                cache.delete(f"biometric_attendance:{att_rid}")

        return JsonResponse({
            'status': 'success',
            'message': f'{action_label} successful',
            'name': official.resident.full_name,
            'time': now.strftime("%I:%M %p"),
            'action': action_label,
            'attendance_status': log.status if 'IN' in action_label else None
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def api_face_recognize(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    return JsonResponse({'status': 'success', 'message': 'Face recognition placeholder', 'recognized': False})


@login_required
def biometric_attendance(request):
    return render(request, 'attendance/biometric_attendance.html')


@login_required
def api_event_attendance_list(request):
    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'status': 'error', 'message': 'Date required'}, status=400)
    try:
        query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'status': 'error', 'message': 'Invalid date format'}, status=400)
    logs = AttendanceLog.objects.filter(date=query_date).select_related('official__resident')
    data = [{'name': l.official.resident.full_name, 'position': l.official.get_position_display(), 'time_in': l.time_in.strftime('%I:%M %p') if l.time_in else '-', 'status': l.get_status_display()} for l in logs]
    return JsonResponse({'status': 'success', 'data': data})


@login_required
def event_attendance_pdf(request):
    date_str = request.GET.get('date')
    event_name = request.GET.get('event_name', 'Event Attendance')
    if not date_str: return HttpResponse('Date required', status=400)
    try: query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError: return HttpResponse('Invalid date format', status=400)
    logs = AttendanceLog.objects.filter(date=query_date).select_related('official__resident').order_by('time_in')
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="attendance_{date_str}.pdf"'
    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    elements.append(Paragraph(f"<b>BARANGAY SICO-SICO MANAGEMENT SYSTEM</b>", styles['Title']))
    elements.append(Paragraph(f"Attendance Report: {event_name}", styles['Heading2']))
    elements.append(Paragraph(f"Date: {query_date.strftime('%B %d, %Y')}", styles['Normal']))
    elements.append(Spacer(1, 12))
    data = [['Official Name', 'Position', 'Time In', 'Status']]
    for log in logs: data.append([log.official.resident.full_name, log.official.get_position_display(), log.time_in.strftime('%I:%M %p') if log.time_in else '-', log.get_status_display()])
    if len(data) == 1: data.append(['No records found', '', '', ''])
    t = Table(data, colWidths=[200, 150, 80, 80])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke), ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, 0), 12), ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.white), ('GRID', (0, 0), (-1, -1), 1, colors.grey)]))
    elements.append(t)
    elements.append(Spacer(1, 24))
    elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Italic']))
    doc.build(elements)
    return response


@login_required
def attendance_history_calendar(request):
    import calendar
    from datetime import date, timedelta
    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    logs = AttendanceLog.objects.filter(date__year=year, date__month=month).values('date', 'status')
    month_data = {}
    for d in range(1, 32):
        try:
            curr_date = date(year, month, d)
            month_data[d] = {'present': 0, 'late': 0, 'absent': 0, 'date_str': curr_date.strftime('%Y-%m-%d')}
        except ValueError: break
    active_officials_count = Official.objects.filter(status='active').count()
    for log in logs:
        d = log['date'].day
        status = log['status']
        if d in month_data:
            if status == 'late': month_data[d]['late'] += 1
            elif status == 'present': month_data[d]['present'] += 1
    
    # Get day off settings
    day_offs = ShiftConfiguration.objects.filter(is_day_off=True).values_list('day', flat=True)
    day_names_inv = {'mon':0, 'tue':1, 'wed':2, 'thu':3, 'fri':4, 'sat':5, 'sun':6}
    day_off_weekdays = [day_names_inv[d] for d in day_offs if d in day_names_inv]

    # Get date-specific overrides (SpecialDate)
    special_dates = {s.date: s.is_day_off for s in SpecialDate.objects.filter(date__year=year, date__month=month)}

    # Calculate absent for each day that has passed or is today
    for d, data in month_data.items():
        curr_date = date(year, month, d)
        data['is_future'] = curr_date > today
        
        # Only SpecialDate overrides mark a day off
        data['is_day_off'] = special_dates.get(curr_date, False)
        
        if not data['is_future']:
            if data['is_day_off']:
                data['absent'] = 0
            else:
                data['absent'] = max(0, active_officials_count - (data['present'] + data['late']))

    cal = calendar.Calendar(firstweekday=6)
    month_days = cal.monthdayscalendar(year, month)
    prev_month_date = date(year, month, 1) - timedelta(days=1)
    next_month_date = date(year, month, 28) + timedelta(days=5)
    next_month_date = next_month_date.replace(day=1)
    
    # Dynamic year range: 5 years back and 5 years forward
    year_range = range(today.year - 5, today.year + 6)
    
    context = {
        'month_days': month_days, 
        'month_name': calendar.month_name[month], 
        'year': year, 
        'month': month, 
        'month_data': month_data, 
        'prev_month': prev_month_date, 
        'next_month': next_month_date, 
        'today': today,
        'year_range': year_range
    }
    return render(request, 'attendance/history_calendar.html', context)


def get_current_week_dates():
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    return {
        'mon': start_of_week,
        'tue': start_of_week + timedelta(days=1),
        'wed': start_of_week + timedelta(days=2),
        'thu': start_of_week + timedelta(days=3),
        'fri': start_of_week + timedelta(days=4),
        'sat': start_of_week + timedelta(days=5),
        'sun': start_of_week + timedelta(days=6),
    }

@login_required
def api_get_shift_settings(request):
    """Fetch all shift configurations from the database."""
    configs = ShiftConfiguration.objects.all()
    week_dates = get_current_week_dates()
    data = {}
    for cfg in configs:
        target_date = week_dates[cfg.day]
        special = SpecialDate.objects.filter(date=target_date).first()
        is_day_off = special.is_day_off if special else cfg.is_day_off
        
        data[cfg.day] = {
            'time_in': cfg.am_in.strftime('%H:%M'),
            'am_out': cfg.am_out.strftime('%H:%M'),
            'pm_in': cfg.pm_in.strftime('%H:%M'),
            'time_out': cfg.pm_out.strftime('%H:%M'),
            'is_day_off': is_day_off,
            'grace_period': cfg.grace_period
        }
    return JsonResponse({'status': 'success', 'settings': data})


@login_required
@csrf_exempt
def api_save_shift_settings(request):
    """Save shift configurations to the database."""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)
    
    try:
        data = json.loads(request.body)
        settings = data.get('settings', {})
        bulk_apply = data.get('bulk_apply', False)
        week_dates = get_current_week_dates()
        
        if bulk_apply:
            # Apply one day's settings to all
            source_day = data.get('source_day', 'mon')
            source_cfg = settings.get(source_day)
            if source_cfg:
                days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']
                for d in days:
                    is_off = source_cfg.get('is_day_off', False) if d == source_day else False
                    
                    ShiftConfiguration.objects.update_or_create(
                        day=d,
                        defaults={
                            'am_in': source_cfg.get('time_in', '08:00'),
                            'am_out': source_cfg.get('am_out', '12:00'),
                            'pm_in': source_cfg.get('pm_in', '13:00'),
                            'pm_out': source_cfg.get('time_out', '17:00'),
                            'grace_period': source_cfg.get('grace_period', 15)
                        }
                    )
                    # Apply day off ONLY to current week
                    SpecialDate.objects.update_or_create(
                        date=week_dates[d],
                        defaults={'is_day_off': is_off, 'description': 'Modal Override'}
                    )
        else:
            # Save individual day settings
            for day, cfg in settings.items():
                ShiftConfiguration.objects.update_or_create(
                    day=day,
                    defaults={
                        'am_in': cfg.get('time_in', '08:00'),
                        'am_out': cfg.get('am_out', '12:00'),
                        'pm_in': cfg.get('pm_in', '13:00'),
                        'pm_out': cfg.get('time_out', '17:00'),
                        'grace_period': cfg.get('grace_period', 15)
                    }
                )
                # Apply day off ONLY to current week
                SpecialDate.objects.update_or_create(
                    date=week_dates[day],
                    defaults={'is_day_off': cfg.get('is_day_off', False), 'description': 'Modal Override'}
                )
        
        return JsonResponse({'status': 'success', 'message': 'Shift settings saved successfully for the current week'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@login_required
def daily_attendance_report(request, date_str):
    try: query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError: return redirect('attendance:history_calendar')
    logs = AttendanceLog.objects.filter(date=query_date).select_related('official__resident').order_by('official__resident__last_name')
    officials = Official.objects.filter(status='active')
    log_dict = {log.official_id: log for log in logs}
    today = datetime.now().date()
    is_future = query_date > today
    
    # Get shift config for threshold
    day_names = {0:'mon', 1:'tue', 2:'wed', 3:'thu', 4:'fri', 5:'sat', 6:'sun'}
    day_code = day_names[query_date.weekday()]
    shift_config = ShiftConfiguration.objects.filter(day=day_code).first()
    
    # Check for date-specific override (SpecialDate)
    special_date = SpecialDate.objects.filter(date=query_date).first()
    if special_date:
        is_day_off = special_date.is_day_off
    else:
        is_day_off = shift_config.is_day_off if shift_config else False
    
    full_report = []
    stats = {'present': 0, 'late': 0, 'absent': 0}

    if not is_future:
        for official in officials:
            log = log_dict.get(official.id)
            if log: full_report.append({'official': official, 'log': log, 'status': log.status})
            else: full_report.append({'official': official, 'log': None, 'status': 'absent'})
        status_order = {'present': 0, 'late': 1, 'absent': 2}
        full_report.sort(key=lambda x: status_order.get(x['status'], 3))
        stats = {
            'present': logs.filter(status='present').count(),
            'late': logs.filter(status='late').count(),
            'absent': len(full_report) - logs.count()
        }
    
    context = {
        'date': query_date, 
        'report': full_report, 
        'stats': stats,
        'today': today,
        'is_future': is_future,
        'shift_config': shift_config,
        'is_day_off': is_day_off
    }
    return render(request, 'attendance/daily_report.html', context)


@login_required
@require_POST
def api_toggle_special_date(request):
    """API to toggle a date as a special day off."""
    date_str = request.POST.get('date')
    if not date_str:
        return JsonResponse({'status': 'error', 'message': 'Date required'}, status=400)
    
    try:
        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        special_date, created = SpecialDate.objects.get_or_create(date=target_date)
        
        # If it was already there, toggle it. If new, default is Day Off (True)
        if not created:
            special_date.is_day_off = not special_date.is_day_off
            special_date.save()
        
        return JsonResponse({
            'status': 'success', 
            'is_day_off': special_date.is_day_off,
            'message': f"Date marked as {'Day Off' if special_date.is_day_off else 'Working Day'}"
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

