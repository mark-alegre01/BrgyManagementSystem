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
]
