from django.db import models
from django.conf import settings
import uuid

class School(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    subdomain = models.CharField(max_length=100, unique=True, help_text="e.g., schoolname")
    logo = models.ImageField(upload_to='school_logos/', null=True, blank=True)
    country = models.CharField(max_length=100)
    address = models.TextField()
    city = models.CharField(max_length=100)  # School location (city/town)
    postal_code = models.CharField(max_length=20)
    num_campuses = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.subdomain:
            self.subdomain = self.name.lower().replace(' ', '-')  # Generate subdomain
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Campus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='campuses')
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)  # Campus location (city/town)
    address = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('school', 'name')  # Unique campus name per school

    def __str__(self):
        return f"{self.name} - {self.school.name}"
