# models.py
from django.db import models
from django.conf import settings

class CalendarEvent(models.Model):
    title = models.CharField(max_length=200)
    start = models.DateTimeField()
    end = models.DateTimeField()
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='events')  # Link event to user

    def __str__(self):
        return f"{self.title} by {self.user.username}"
