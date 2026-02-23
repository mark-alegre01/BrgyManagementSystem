from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from residents.models import Resident
from certifications.models import Certificate
from attendance.models import AttendanceLog
from officials.models import Official
from ordinances.models import Ordinance
from datetime import date, timedelta


@login_required
def reports_dashboard(request):
    """Reports dashboard with summary data."""
    today = date.today()
    month_start = today.replace(day=1)

    context = {
        # Population
        'total_population': Resident.objects.filter(is_active=True).count(),
        'male_count': Resident.objects.filter(is_active=True, gender='M').count(),
        'female_count': Resident.objects.filter(is_active=True, gender='F').count(),
        'voters': Resident.objects.filter(is_registered_voter=True).count(),

        # Certificates this month
        'certs_this_month': Certificate.objects.filter(date_issued__gte=month_start).count(),
        'cert_breakdown': [
            {'type': dict(Certificate.TYPE_CHOICES).get(item['cert_type'], item['cert_type'].replace('_', ' ').title()), 'count': item['count']}
            for item in Certificate.objects.filter(date_issued__gte=month_start).values('cert_type').annotate(count=Count('id'))
        ],
        'total_revenue': Certificate.objects.filter(date_issued__gte=month_start).aggregate(total=Sum('amount_paid'))['total'] or 0,

        # Attendance
        'attendance_today': AttendanceLog.objects.filter(date=today).count(),

        # Officials
        'active_officials': Official.objects.filter(status='active').count(),

        # Ordinances
        'total_ordinances': Ordinance.objects.count(),
        'active_ordinances': Ordinance.objects.filter(status='active').count(),
    }
    return render(request, 'reports/dashboard.html', context)
