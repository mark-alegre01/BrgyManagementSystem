from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("residents.urls")),
    path("census/", include("census.urls")),
    path("officials/", include("officials.urls")),
    path("attendance/", include("attendance.urls")),
    path("certifications/", include("certifications.urls")),
    path("reports/", include("reports.urls")),
    path("philsys/", include("philsys.urls")),
    path("login/", core_views.login_view, name="login"),
    path("logout/", core_views.logout_view, name="logout"),
    path("signup/", core_views.signup_view, name="signup"),
    path(
        "dashboard/",
        lambda request: __import__("residents.views", fromlist=["dashboard"]).dashboard(
            request
        ),
        name="dashboard",
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
