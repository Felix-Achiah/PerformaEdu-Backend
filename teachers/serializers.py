from rest_framework import serializers
from django.db import transaction
from student_performance.models import TeacherLevelClass

class MainTeacherAssignmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherLevelClass
        fields = ['teacher', 'class_id', 'is_main_teacher']  # Fields required for assigning main teacher

    def update(self, instance, validated_data):
        with transaction.atomic():
            if validated_data.get('is_main_teacher', False):
                TeacherLevelClass.objects.filter(class_id=instance.class_id, is_main_teacher=True).update(is_main_teacher=False)
            instance.is_main_teacher = validated_data.get('is_main_teacher', instance.is_main_teacher)
            instance.save()
        return instance
