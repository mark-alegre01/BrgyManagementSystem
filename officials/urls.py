from django.urls import path
from . import views

app_name = 'officials'

urlpatterns = [
    path('', views.official_list, name='list'),
    path('add/', views.official_add, name='add'),
    path('<int:pk>/', views.official_view, name='view'),
    path('<int:pk>/edit/', views.official_edit, name='edit'),
    path('<int:pk>/delete/', views.official_delete, name='delete'),
]
