from django.db import models
from django.conf import settings

class NotificationPreference(models.Model):
    NOTIFICATION_TYPES = [
        ('email', 'Email'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='email')
    is_active = models.BooleanField(default=True)  # Track if the notification type is active

    def __str__(self):
        return f"{self.user.username}'s {self.notification_type.capitalize()} Notification Preference"
