from django.urls import path
from .views import AnnouncementAPIView

urlpatterns = [
    path('announcements/', AnnouncementAPIView.as_view(), name='announcement-list-create'),  # For listing and creating
    path('announcement/<int:announcement_id>/', AnnouncementAPIView.as_view()),  # For retrieving, updating, deleting
]
