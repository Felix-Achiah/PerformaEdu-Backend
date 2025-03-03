# serializers.py
from rest_framework import serializers
from .models import CalendarEvent

class CalendarEventSerializer(serializers.ModelSerializer):
    user = serializers.ReadOnlyField(source='user.username')  # Read-only field for user
    user_id = serializers.ReadOnlyField(source='user.id')

    class Meta:
        model = CalendarEvent
        fields = ['id', 'title', 'start', 'end', 'user', 'user_id']
