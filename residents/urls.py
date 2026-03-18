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
]
