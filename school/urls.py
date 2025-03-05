from django.urls import path
from . import views

urlpatterns = [
    path('school-signup/', views.SchoolSignupView.as_view(), name='school-signup'),
    path('schools/', views.SchoolListView.as_view(), name='schools'),
]