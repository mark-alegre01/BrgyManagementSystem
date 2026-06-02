from django.urls import path
from . import views

app_name = 'ordinances'

urlpatterns = [
    path('', views.ordinance_list, name='list'),
    path('add/', views.ordinance_add, name='add'),
    path('<int:pk>/', views.ordinance_view, name='view'),
    path('<int:pk>/edit/', views.ordinance_edit, name='edit'),
    path('<int:pk>/delete/', views.ordinance_delete, name='delete'),
    path('<int:pk>/download/', views.ordinance_download, name='download'),
    path('upload-parse/', views.ordinance_upload_parse, name='upload_parse'),
]
