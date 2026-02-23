from django.urls import path
from . import views

app_name = 'certifications'

urlpatterns = [
    path('', views.certificate_list, name='list'),
    path('issue/', views.certificate_issue, name='issue'),
    path('<int:pk>/', views.certificate_view, name='view'),
    path('<int:pk>/pdf/', views.certificate_pdf, name='pdf'),
    path('search/', views.certificate_search, name='search'),
]
