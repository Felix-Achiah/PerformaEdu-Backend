from rest_framework import serializers
from .models import NotificationPreference

class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = ['notification_type', 'is_active']

    def validate_notification_type(self, value):
        if value not in ['email']:
            raise serializers.ValidationError("Invalid notification type.")
        return value
