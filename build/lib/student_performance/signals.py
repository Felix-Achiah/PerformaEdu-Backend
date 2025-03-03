from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Assessment, ProcessedMarks, ClassEnrollment
from .utils import calculate_processed_marks  # A utility function to handle calculations

@receiver(post_save, sender=Assessment)
@receiver(post_delete, sender=Assessment)
def update_processed_marks(sender, instance, **kwargs):
    """
    Update or create ProcessedMarks whenever an Assessment is added, updated, or deleted.
    """
    class_id = instance.class_id
    semester = instance.semester
    student = instance.student_id

    # Recalculate processed marks for the specific student
    calculate_processed_marks(class_id, semester, student)
