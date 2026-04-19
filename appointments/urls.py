from django.urls import path
from . import views

urlpatterns = [
    path('book/', views.book_appointment, name='book_appointment'),
    path('list/', views.appointment_list, name='appointment_list'),
    path('update/<int:pk>/<str:status>/', views.appointment_status_update, name='appointment_status_update'),
]
