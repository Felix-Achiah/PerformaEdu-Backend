# urls.py
from django.urls import path
from .views import CalendarEventListCreateView, CalendarEventRetrieveUpdateDestroyView, UserCalendarEventListView

urlpatterns = [
    path('events/', CalendarEventListCreateView.as_view(), name='event-list-create'),
    path('events/<int:pk>/', CalendarEventRetrieveUpdateDestroyView.as_view(), name='event-retrieve-update-destroy'),
    path('events/user/<int:user_id>/', UserCalendarEventListView.as_view(), name='user-events-list'),
]
