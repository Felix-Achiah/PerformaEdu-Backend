import uuid
from django.db import models
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from datetime import date

from administrator.models import AcademicYear
from school.models import School, Campus


CRECHE = 'Creche'
PRIMARY = 'Primary'
JHS = 'Jhs'
SHS = 'Shs'

LEVEL_TYPE_CHOICES = [
    (CRECHE, 'Creche'),
    (PRIMARY, 'Primary'),
    (JHS, 'Jhs'),
    (SHS, 'Shs'),
]

class Level(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_levels', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_levels', null=True, blank=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Terms(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='schoo_terms', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='school_terms', null=True, blank=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Class(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_classes', null=True, blank=True) # All classes in the school
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_classes', null=True, blank=True)
    name = models.CharField(max_length=100)
    level = models.ForeignKey(Level, on_delete=models.CASCADE, related_name='classes', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)
    
    def __str__(self):
        return self.name
    

class Subject(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_subjects', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_subjects', null=True, blank=True)
    name = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return self.name


class ClassSubject(models.Model):
    """
    Model to link Subjects to Classes.
    Different classes can have the same subjects.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, null=True, blank=True, related_name="school_class_subjects")
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, null=True, blank=True, related_name="campus_class_subjects")
    class_id = models.ForeignKey('Class', on_delete=models.CASCADE, related_name="subjects_assigned")
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, related_name="classes_assigned")
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('class_id', 'subject')  # Prevent duplicate subject assignments to the same class

    def __str__(self):
        return f"{self.class_id.name} - {self.subject.name}"



class TeacherLevelClass(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_teacher_level_class', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_teacher_level_class', null=True, blank=True)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='teacher_level_classes'
    )
    class_id = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name='student_teacher_level_classes'
    )
    subjects_taught = models.ManyToManyField(
        Subject,
        related_name='teacher_level_classes',
        blank=True  # Allow no subjects
    )
    is_main_teacher = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f'{self.teacher.username} - Class: {self.class_id.name}, Main Teacher: {self.is_main_teacher}'

    def save(self, *args, **kwargs):
        # Ensure that there is only one main teacher per class
        if self.is_main_teacher:
            TeacherLevelClass.objects.filter(class_id=self.class_id, is_main_teacher=True).update(is_main_teacher=False)
        
        super(TeacherLevelClass, self).save(*args, **kwargs)


class TeacherAssignmentHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_teacher_assignment_history', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_teacher_assignment_history', null=True, blank=True)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE)
    subjects_taught = models.ManyToManyField('Subject')
    unassigned_at = models.DateTimeField(auto_now_add=True)  # Timestamp when unassigned

    def __str__(self):
        return f"{self.teacher} - {self.class_id} (Unassigned on {self.unassigned_at})"


class Student(models.Model):
    username = models.CharField(max_length=100)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=50, null=True)
    student_profile_pic = models.ImageField(upload_to='student_profile_pic/', null=True)
    created_at = models.DateField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateField(auto_now=True)

    class Meta:
        verbose_name = 'Student'
        verbose_name_plural = 'Students'

    def __str__(self):
        return self.name
    
    @property
    def age(self):
        if self.date_of_birth:
            today = date.today()
            return today.year - self.date_of_birth.year - (
                (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        return None
    
class StudentParentRelation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_student_parent_relation', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_student_parent_relation', null=True, blank=True)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        limit_choices_to={'roles__name': 'Student'},
        on_delete=models.CASCADE,
        related_name="parent_relations"  # Add related_name to avoid clashes
    )
    parent = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        limit_choices_to={'roles__name': 'Parent'},  
        on_delete=models.CASCADE,
        related_name="children_relations"  # Add related_name to avoid clashes
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'parent'], name='unique_parent_student'),
        ]
        unique_together = ['student', 'parent']

    def __str__(self):
        return f'{self.parent} - {self.student}'


class AssessmentName(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_assessment_names', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_assessment_names', null=True, blank=True)
    name = models.CharField(max_length=255)
    class_id = models.ForeignKey(
        Class,
        on_delete=models.CASCADE,
        related_name='assessment_names',
        null=True,
        blank=True
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='assessment_names',
        null=True,
        blank=True
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_assessment_names',
        null=True,  # Allow null for system-wide assessments
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    class Meta:
        unique_together = ('name', 'class_id', 'subject', 'teacher')  # Unique per teacher-subject-class combo

    def __str__(self):
        return f"{self.name} - {self.class_id.name} - {self.subject.name} ({self.teacher.username if self.teacher else 'System'})"


class Assessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_assessments', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_assessments', null=True, blank=True)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        limit_choices_to={'roles__name': 'Student'},  
        on_delete=models.CASCADE, 
        null=True
    )
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE, null=True)
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='student_assessment', 
        null=True
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200, null=True, blank=True)
    comments = models.TextField(null=True, blank=True)
    assessment_name = models.ForeignKey(
        AssessmentName,
        on_delete=models.SET_NULL,  # Preserve assessment if name is deleted
        related_name='assessments',
        null=True,
        blank=True
    )
    term = models.ForeignKey(Terms, on_delete=models.CASCADE, null=True, blank=True)
    total_marks = models.DecimalField(max_digits=5, decimal_places=2)
    obtained_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    created_at = models.DateField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.subject.name} - {self.assessment_type} - {self.term_id} - {self.date}"


class ProcessedMarks(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_processed_marks', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_processed_marks', null=True, blank=True)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        limit_choices_to={'roles__name': 'Student'},  
        on_delete=models.CASCADE
    )
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE)
    term = models.ForeignKey(Terms, on_delete=models.SET_NULL, null=True, blank=True)
    total_score = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=20)
    subject_data = models.JSONField()  
    position = models.CharField(max_length=10, blank=True)  
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.student.username} - {self.class_id.name} - {self.semester}"


class SubjectPerformance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_subject_performance', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_subject_performance', null=True, blank=True)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        limit_choices_to={'roles__name': 'Student'},  
        on_delete=models.CASCADE
    )
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, null=True, blank=True)
    term = models.ForeignKey(Terms, on_delete=models.SET_NULL, null=True, blank=True)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"{self.student.username} - {self.subject.name} - {self.academic_year} - {self.semester}"


class ClassEnrollment(models.Model):
    STATUS_CHOICES = [
        ('existing', 'Existing'),
        ('promoted', 'Promoted'),
        ('repeated', 'Repeated'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_class_enrollment', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_class_enrollment', null=True, blank=True)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='class_enrollment', 
        limit_choices_to={'roles__name': 'Student'},  
        on_delete=models.CASCADE
    )
    class_id = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, null=True, blank=True)
    term = models.ForeignKey(Terms, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='existing')
    created_at = models.DateField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.student.username} - {self.class_id.name} ({self.academic_year})"


class HistoricalClassEnrollment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_historical_class_enrollment', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_historical_class_enrollment', null=True, blank=True)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        related_name='historical_class_enrollment', 
        limit_choices_to={'roles__name': 'Student'},  
        on_delete=models.CASCADE
    )
    class_enrolled = models.ForeignKey(Class, on_delete=models.CASCADE)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, null=True, blank=True)
    term = models.ForeignKey(Terms, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.student.username} - {self.class_enrolled.name} - {self.academic_year} - {self.term}"


class HistoricalAssessmentResult(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_historical_assessment_result', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_historical_assessment_result', null=True, blank=True)
    historical_class_enrollment = models.ForeignKey(HistoricalClassEnrollment, on_delete=models.CASCADE)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.historical_class_enrollment.student.name} - {self.assessment.topic}"


class TimeTable(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='school_timetables', null=True, blank=True)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name='campus_timetables', null=True, blank=True)
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="timetables")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    day = models.CharField(max_length=20)  # e.g., "Monday"
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.class_id.name} - {self.subject.name} on {self.day}"