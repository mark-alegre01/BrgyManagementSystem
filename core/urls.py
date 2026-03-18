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
]
