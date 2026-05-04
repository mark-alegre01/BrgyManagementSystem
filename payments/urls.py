from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('dashboard/', views.payment_dashboard, name='dashboard'),
    path('<int:payment_id>/pay-cash/', views.mark_as_paid, name='mark_paid'),
    path('<int:payment_id>/confirm-gcash/', views.confirm_gcash_payment, name='confirm_gcash'),
    path('<int:payment_id>/waive/', views.waive_fee, name='waive_fee'),
    path('request/<int:request_id>/pay/', views.resident_choose_payment, name='choose_payment'),
    path('<int:payment_id>/receipt/', views.download_receipt, name='download_receipt'),
]
