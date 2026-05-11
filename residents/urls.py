from django.urls import path
from . import views

app_name = 'residents'

urlpatterns = [
    path('', views.resident_list, name='list'),
    path('add/', views.resident_add, name='add'),
    path('<int:pk>/', views.resident_view, name='view'),
    path('<int:pk>/edit/', views.resident_edit, name='edit'),
    path('<int:pk>/delete/', views.resident_delete, name='delete'),
    path('households/', views.household_list, name='household_list'),
    path('households/add/', views.household_add, name='household_add'),
    path('households/<int:pk>/', views.household_view, name='household_view'),
    path('<int:pk>/capture/', views.resident_capture_fingerprint, name='capture_fingerprint'),
    path('<int:pk>/fingerprint/', views.resident_update_fingerprint, name='update_fingerprint'),
    # Registration Verification
    path('registrations/', views.registration_list, name='registration_list'),
    path('registrations/<int:pk>/', views.registration_detail, name='registration_detail'),
    path('registrations/<int:pk>/approve/', views.approve_registration, name='approve_registration'),
    path('registrations/<int:pk>/reject/', views.reject_registration, name='reject_registration'),
    path('purok/add/', views.purok_add_api, name='purok_add_api'),
    path('fingerprint-lookup/', views.get_resident_by_fingerprint, name='fingerprint_lookup'),
]
