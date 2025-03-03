from rest_framework import serializers

from .models import AcademicYear
from student_performance.models import TeacherLevelClass, Subject, Class


class AssignSubjectsToTeachersSerializer(serializers.ModelSerializer):
    class_id = serializers.PrimaryKeyRelatedField(queryset=Class.objects.all())
    subjects_taught = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.all(), many=True)

    class Meta:
        model = TeacherLevelClass
        fields = ['teacher', 'class_id', 'subjects_taught', 'is_main_teacher']


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ['id', 'start_year', 'end_year', 'is_active']