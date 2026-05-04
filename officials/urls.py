from django.urls import path
from . import views

app_name = 'officials'

urlpatterns = [
    path('', views.official_list, name='list'),
    path('add/', views.official_add, name='add'),
    path('api/by-category/', views.get_officials_by_category, name='get_by_category'),
    path('biometric/register/', views.biometric_register, name='biometric_register'),
    path('biometric/status/', views.biometric_status, name='biometric_status'),
    path('<int:pk>/', views.official_view, name='official_view'),
    path('<int:pk>/capture/', views.official_capture_fingerprint, name='official_capture_fingerprint'),
    path('<int:pk>/update-fingerprint/', views.official_update_fingerprint, name='official_update_fingerprint'),
    path('profile/<int:pk>/update-fingerprint/', views.profile_update_fingerprint, name='profile_update_fingerprint'),
    path('<int:pk>/edit/', views.official_edit, name='edit'),
    path('<int:pk>/delete/', views.official_delete, name='delete'),
    
    # Onboarding Flows
    path('onboarding/invite/', views.invite_official, name='invite_official'),
    path('onboarding/approvals/', views.onboard_approvals_list, name='onboard_approvals_list'),
    path('onboarding/<uuid:token>/upload/', views.onboard_upload_docs, name='onboard_upload_docs'),
    path('onboarding/<uuid:token>/approve/', views.onboard_approve, name='onboard_approve'),
    path('onboarding/<uuid:token>/activate/', views.onboard_verify_otp, name='onboard_verify_otp'),
]
