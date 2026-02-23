from django.urls import path
from . import views

app_name = 'census'

urlpatterns = [
    path('', views.census_dashboard, name='dashboard'),
    path('age-groups/', views.age_groups, name='age_groups'),
    path('demographics/', views.demographics, name='demographics'),
]
