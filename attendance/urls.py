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
]
