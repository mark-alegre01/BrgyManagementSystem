from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),

    # Biometric APIs
    path('biometric-templates/', views.biometric_templates, name='biometric_templates'),
    path('biometric-verify-login/', views.biometric_verify_login, name='biometric_verify_login'),
    path('biometric-verify-login-start/', views.biometric_verify_login_start, name='biometric_verify_login_start'),
    path('biometric-login-start/', views.biometric_login_start, name='biometric_login_start'),
    path('biometric-status-check/', views.biometric_status_check, name='biometric_status_check'),
    path('backup/choose/', views.backup_setup, name='backup_setup'),
    path('backup/download/', views.backup_download, name='backup_download'),
    path('backup/execute/', views.backup_execute, name='backup_execute'),
    path('backup/mount/', views.backup_mount_drive, name='backup_mount_drive'),
    path('backup/check-dests/', views.backup_check_dests, name='backup_check_dests'),
    # Notifications
    path('notifications/', views.notifications_view, name='notifications'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark_notification_read'),
]
