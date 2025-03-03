# views.py
from rest_framework import generics
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from .models import CalendarEvent
from .serializers import CalendarEventSerializer
from user_auth.permissions import IsParent, IsHeadmaster, IsTeacher

class CalendarEventListCreateView(generics.ListCreateAPIView):
    """
    Handles listing and creating calendar events for the authenticated user.
    """
    serializer_class = CalendarEventSerializer
    permission_classes = [IsAuthenticated, IsHeadmaster | IsTeacher | IsParent]

    def get_queryset(self):
        """
        Return events that belong to the currently authenticated user.
        """
        return CalendarEvent.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        """
        Automatically set the user when creating a calendar event.
        """
        serializer.save(user=self.request.user)


class UserCalendarEventListView(generics.ListAPIView):
    """
    List all events for a specific user.
    """
    permission_classes = [IsAuthenticated, IsHeadmaster | IsTeacher | IsParent]
    serializer_class = CalendarEventSerializer

    def get_queryset(self):
        user_id = self.kwargs['user_id']
        return CalendarEvent.objects.filter(user_id=user_id)



class CalendarEventRetrieveUpdateDestroyView(generics.RetrieveUpdateDestroyAPIView):
    """
    Handles retrieving, updating, and deleting a specific calendar event.
    """
    permission_classes = [IsAuthenticated, IsHeadmaster | IsTeacher | IsParent]

    queryset = CalendarEvent.objects.all()
    serializer_class = CalendarEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """
        Ensure that users can only interact with their own events.
        """
        print(f"User ID: {self.request.user.id}")  # Log user ID
        user_events = CalendarEvent.objects.filter(user=self.request.user)
        print(f"Events for user {self.request.user.id}: {user_events}")  # Log the filtered events
        return user_events

