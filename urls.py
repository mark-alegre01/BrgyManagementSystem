from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('residents.urls')),
    path('households/', include('households.urls')),
    path('officials/', include('officials.urls')),
    path('attendance/', include('attendance.urls')),
    path('certifications/', include('certifications.urls')),
    path('reports/', include('reports.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    path('dashboard/', lambda request: __import__('residents.views', fromlist=['dashboard']).dashboard(request), name='dashboard'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
