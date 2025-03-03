from django.db import models
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from datetime import date


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


class Class(models.Model):
    name = models.CharField(max_length=100)
    level_type = models.CharField(max_length=100, choices=LEVEL_TYPE_CHOICES)
    
    def __str__(self):
        return self.name
    

class Subject(models.Model):
    name = models.CharField(max_length=100)
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE, null=True, blank=True)

    def __str__(self):
        return self.name


class TeacherLevelClass(models.Model):
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teacher_level_classes')
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE, related_name='student_teacher_level_classes')
    subjects_taught = models.ManyToManyField(Subject, related_name='teacher_level_classes')
    is_main_teacher = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.teacher.username} - Class: {self.class_id.name}, Main Teacher: {self.is_main_teacher}'

    def save(self, *args, **kwargs):
        # Ensure that there is only one main teacher per class
        if self.is_main_teacher:
            TeacherLevelClass.objects.filter(class_id=self.class_id, is_main_teacher=True).update(is_main_teacher=False)
        
        super(TeacherLevelClass, self).save(*args, **kwargs)


class Student(models.Model):
    name = models.CharField(max_length=100)
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
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    parent = models.ForeignKey(settings.AUTH_USER_MODEL, limit_choices_to={'user_type': 'Parent'}, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['student', 'parent'], name='unique_parent_student'),
            models.UniqueConstraint(fields=['student'], name='max_two_parents'),
        ]
        unique_together = ['student', 'parent']

    def __str__(self):
        return f'{self.parent} - {self.student}'

class Assessment(models.Model):
    SEMESTER_CHOICES = [
        ('1st Semester', 'Semester 1'),
        ('2nd Semester', 'Semester 2'),
    ]

    student_id = models.ForeignKey(Student, on_delete=models.CASCADE, null=True)
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE, null=True)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_assessment', null=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    topic = models.CharField(max_length=200, null=True, blank=True)
    assessment_type = models.CharField(max_length=20)  # Exercise, Assignment, MidTermExam, etc.
    semester = models.CharField(max_length=50, choices=SEMESTER_CHOICES)
    total_marks = models.DecimalField(max_digits=5, decimal_places=2)
    obtained_marks = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    date = models.DateField(null=True, blank=True)
    created_at = models.DateField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.subject.name} - {self.assessment_type} - {self.semester}"


class ProcessedMarks(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE)
    semester = models.CharField(max_length=20)
    total_score = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=20)
    subject_data = models.JSONField()  # Store subject data as JSON
    position = models.CharField(max_length=10, blank=True)  # Position with suffix
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.name} - {self.class_id.name} - {self.semester}"


class SubjectPerformance(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    class_id = models.ForeignKey('Class', on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=20)
    semester = models.CharField(max_length=50, choices=Assessment.SEMESTER_CHOICES)
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'))

    def __str__(self):
        return f"{self.student.name} - {self.subject.name} - {self.academic_year} - {self.semester}"

class ClassEnrollment(models.Model):
    STATUS_CHOICES = [
        ('existing', 'Existing'),
        ('promoted', 'Promoted'),
        ('repeated', 'Repeated'),
    ]

    student = models.ForeignKey(Student, related_name='class_enrollment', on_delete=models.CASCADE)
    class_id = models.ForeignKey(Class, on_delete=models.SET_NULL, null=True)
    academic_year = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='existing')
    created_at = models.DateField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateField(auto_now=True)

    def __str__(self):
        return f"{self.student.name} - {self.class_id.name} ({self.academic_year})"


class HistoricalClassEnrollment(models.Model):
    student = models.ForeignKey(Student, related_name='historical_class_enrollment', on_delete=models.CASCADE)
    class_enrolled = models.ForeignKey(Class, on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.student.name} - {self.class_enrolled.name} - {self.academic_year}"


class HistoricalAssessmentResult(models.Model):
    historical_class_enrollment = models.ForeignKey(HistoricalClassEnrollment, on_delete=models.CASCADE)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.historical_class_enrollment.student.name} - {self.assessment.topic}"


class TimeTable(models.Model):
    class_id = models.ForeignKey(Class, on_delete=models.CASCADE, related_name="timetables")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, null=True, blank=True)
    teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    day = models.CharField(max_length=20)  # e.g., "Monday"
    start_time = models.TimeField()
    end_time = models.TimeField()

    def __str__(self):
        return f"{self.class_id.name} - {self.subject.name} on {self.day}"