from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('residents/', include('residents.urls')),
    path('certifications/', include('certifications.urls')),
    path('attendance/', include('attendance.urls')),
    path('census/', include('census.urls')),
    path('ordinances/', include('ordinances.urls')),
    path('officials/', include('officials.urls')),
    path('reports/', include('reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
