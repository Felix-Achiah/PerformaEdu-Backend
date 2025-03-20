import uuid
from django.db import models

from school.models import School, Campus

class AcademicYear(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, null=True, blank=True)
    start_year = models.IntegerField()
    end_year = models.IntegerField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_year']  # Latest academic year first

    def __str__(self):
        return f"{self.start_year}/{self.end_year}"
