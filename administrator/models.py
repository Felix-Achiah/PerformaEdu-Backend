from django.db import models

class AcademicYear(models.Model):
    start_year = models.IntegerField()
    end_year = models.IntegerField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_year']  # Latest academic year first

    def __str__(self):
        return f"{self.start_year}/{self.end_year}"
