from django.urls import path
from . import views

app_name = 'documents'

urlpatterns = [
    path('', views.DocumentListView.as_view(), name='list'),
    path('workspace/', views.DocumentCreateView.as_view(), name='workspace'),
    path('<int:pk>/edit/', views.DocumentUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.DocumentDeleteView.as_view(), name='delete'),
    path('<int:pk>/pdf/', views.DocumentPDFView.as_view(), name='pdf'),
]
