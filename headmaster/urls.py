from django.urls import path
from . import views

urlpatterns = [
    path('headmaster-dashboard/statistics/', views.HeadMasterDashboardStatisticsView.as_view(), name='headmaster_dashboard_statistics'),
]
