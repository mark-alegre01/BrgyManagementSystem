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
]
