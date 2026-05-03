from django.urls import path
from . import views

app_name = 'certifications'

urlpatterns = [
    path('', views.certificate_list, name='list'),
    path('issue/', views.certificate_issue, name='issue'),
    path('<int:pk>/', views.certificate_view, name='view'),
    path('<int:pk>/pdf/', views.certificate_pdf, name='pdf'),
    path('<int:pk>/receipt/', views.certificate_receipt_pdf, name='receipt'),
    path('search/', views.certificate_search, name='search'),
    path('check-uniqueness/', views.check_uniqueness, name='check_uniqueness'),
    path('get-next-numbers/', views.get_next_numbers, name='get_next_numbers'),
    path('<int:pk>/delete/', views.certificate_delete, name='delete'),
    # Certificate Requests
    path('requests/', views.request_list, name='request_list'),
    path('requests/new/', views.request_certificate, name='request_certificate'),
    path('my-requests/', views.my_requests, name='my_requests'),
    path('requests/<int:pk>/fulfill/', views.fulfill_request, name='fulfill_request'),
    path('requests/<int:pk>/reject/', views.reject_request, name='reject_request'),
    path('<int:pk>/virtual/', views.virtual_certificate, name='virtual_certificate'),
]
