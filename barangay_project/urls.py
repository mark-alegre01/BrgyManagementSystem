from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.decorators.csrf import csrf_exempt
from core import views as core_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', core_views.login_view, name='login'),
    path('logout/', core_views.logout_view, name='logout'),
    path('signup/', core_views.signup_view, name='signup'),
    path('resident-signup/', core_views.resident_signup_view, name='resident_signup'),
    path('registration-success/<str:ref>/', core_views.registration_success_view, name='registration_success'),
    path('dashboard/', core_views.dashboard, name='dashboard'),
    path('biometric-login-start/', csrf_exempt(core_views.biometric_login_start), name='biometric_login_start'),
    path('biometric-status-check/', csrf_exempt(core_views.biometric_status_check), name='biometric_status_check'),
    path('', include('core.urls')),
    path('residents/', include('residents.urls')),
    path('certifications/', include('certifications.urls')),
    path('attendance/', include('attendance.urls')),
    path('census/', include('census.urls')),
    path('ordinances/', include('ordinances.urls')),
    path('officials/', include('officials.urls')),
    path('reports/', include('reports.urls')),
    path('appointments/', include('appointments.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
