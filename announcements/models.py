import uuid
from django.db import models

from school.models import School, Campus

class Announcement(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school= models.ForeignKey(School, on_delete=models.CASCADE, null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=255)
    date = models.DateField()
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
