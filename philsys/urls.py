from django.urls import path
from . import views

app_name = "philsys"

urlpatterns = [
    path("verify/", views.verify_philsys, name="verify"),
    path("verify/qr/", views.verify_qr_code, name="verify_qr"),
    path("verify/psn/", views.verify_psn, name="verify_psn"),
    path("status/<int:attempt_id>/", views.get_verification_status, name="status"),
    path("history/", views.verification_history, name="history"),
    path("check/<int:resident_id>/", views.check_verification, name="check"),
]
