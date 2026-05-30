from django.urls import path
from . import views

app_name = 'attendance'

urlpatterns = [
    path('', views.attendance_dashboard, name='dashboard'),
    path('clock/', views.clock_in_out, name='clock'),
    path('enroll/', views.face_enroll, name='enroll'),
    path('dtr/', views.dtr_list, name='dtr'),
    path('dtr/<int:official_id>/', views.dtr_detail, name='dtr_detail'),
    path('dtr/<int:official_id>/print/', views.dtr_print, name='dtr_print'),
    path('api/recognize/', views.api_face_recognize, name='api_recognize'),
    path('public-scan/', views.public_dtr_scan, name='public_scan'),
    path('api/biometric-verify/', views.api_biometric_verify, name='api_biometric_verify'),
    path('biometric-attendance/', views.biometric_attendance, name='biometric_attendance'),
    path('api/event-attendance-list/', views.api_event_attendance_list, name='api_event_attendance_list'),
    path('api/event-attendance-pdf/', views.event_attendance_pdf, name='event_attendance_pdf'),
    path('history/', views.attendance_history_calendar, name='history_calendar'),
    path('history/<str:date_str>/', views.daily_attendance_report, name='daily_report'),
    path('api/shift-settings/', views.api_get_shift_settings, name='api_get_shift_settings'),
    path('api/shift-settings/save/', views.api_save_shift_settings, name='api_save_shift_settings'),
    path('api/toggle-special-date/', views.api_toggle_special_date, name='api_toggle_special_date'),
    
    # Work Scheduling
    path('schedule/', views.work_schedule_view, name='work_schedule'),
    path('api/schedule/generate/', views.api_generate_schedule, name='api_generate_schedule'),
    path('api/schedule/update/', views.api_update_schedule, name='api_update_schedule'),
    path('api/schedule/replacements/', views.api_get_replacements, name='api_get_replacements'),
]
