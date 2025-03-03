from django.urls import path
from . import views

urlpatterns = [
    path('update-notifications/', views.update_notification_preference, name='update-notifications'),
]
