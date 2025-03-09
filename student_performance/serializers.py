from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import Class, TeacherLevelClass, TeacherAssignmentHistory , Subject, Assessment, ClassEnrollment, Student, HistoricalClassEnrollment, SubjectPerformance, ProcessedMarks, Level, Terms, StudentParentRelation, TimeTable, AssessmentName
from user_auth.serializers import UserSerializer
from school.serializers import SchoolSerializer, CampusSerializer

User = get_user_model()


class LevelSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    campus_name = serializers.CharField(source='campus.name', read_only=True)

    class Meta:
        model = Level
        fields = ['id', 'school', 'school_name', 'campus', 'campus_name', 'name']
        extra_kwargs = {
            'school': {'required': False},  # Optional, can be null
            'campus': {'required': False},  # Optional, can be null
        }

    def create(self, validated_data):
        return Level.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.school = validated_data.get('school', instance.school)
        instance.campus = validated_data.get('campus', instance.campus)
        instance.name = validated_data.get('name', instance.name)
        instance.save()
        return instance


class TermsSerializer(serializers.ModelSerializer):
    school_name = serializers.CharField(source='school.name', read_only=True)
    campus_name = serializers.CharField(source='campus.name', read_only=True)

    class Meta:
        model = Terms
        fields = ['id', 'school', 'school_name', 'campus', 'campus_name', 'name']
        extra_kwargs = {
            'school': {'required': False},  # Optional, can be null
            'campus': {'required': False},  # Optional, can be null
        }

    def create(self, validated_data):
        return Terms.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.school = validated_data.get('school', instance.school)
        instance.campus = validated_data.get('campus', instance.campus)
        instance.name = validated_data.get('name', instance.name)
        instance.save()
        return instance


class ClassSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)  # Serialize school
    campus = CampusSerializer(read_only=True)  # Serialize campus
    level = serializers.CharField(source='level_type', read_only=True)  # Rename level_type to level
    class Meta:
        model = Class
        fields = ['id', 'name', 'level_type', 'level', 'school', 'campus', 'created_at', 'updated_at']


class ClassEnrollmentSerializer(serializers.ModelSerializer):
    student = UserSerializer()
    school = SchoolSerializer(read_only=True)  # Serialize school
    campus = CampusSerializer(read_only=True)  # Serialize campus
    level = LevelSerializer(read_only=True)  # Serialize level
    term = TermsSerializer(read_only=True)  # Serialize terms
    class_name = serializers.SerializerMethodField()
    academic_year = serializers.SerializerMethodField()
    level_type = serializers.CharField(source='class_id.level_type', allow_null=True)

    class Meta:
        model = ClassEnrollment
        fields = ['id', 'student', 'class_id', 'class_name', 'academic_year', 'status', 'level_type', 'level', 'term', 'school', 'campus', 'created_at', 'updated_at']

    def get_class_name(self, obj):
        return obj.class_id.name if obj.class_id else None

    def get_academic_year(self, obj):
        if obj.academic_year:
            return f"{obj.academic_year.start_year}-{obj.academic_year.end_year}"
        return None

class HistoricalClassEnrollmentSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    campus = CampusSerializer(read_only=True)
    term = TermsSerializer(read_only=True)
    student = UserSerializer()
    class_name = serializers.SerializerMethodField()

    class Meta:
        model = HistoricalClassEnrollment
        fields = ['id', 'student', 'class_enrolled', 'class_name', 'academic_year', 'term', 'school', 'campus']

    def get_class_name(self, obj):
        return obj.class_enrolled.name


class StudentSerializer(serializers.ModelSerializer):
    class_enrollment = ClassEnrollmentSerializer(read_only=True, many=True)
    historical_class_enrollment = HistoricalClassEnrollmentSerializer(read_only=True, many=True)
    

    class Meta:
        model = Student
        fields = ['id', 'username', 'date_of_birth', 'age', 'gender', 'created_at', 'updated_at', 'class_enrollment', 'historical_class_enrollment']

    def get_current_class_id(self, obj):
        # Fetch the current enrollment for the student
        enrollment = ClassEnrollment.objects.filter(student=obj).first()
        return enrollment.class_id.id if enrollment else None

    def create(self, validated_data):
        class_enrollment_data = validated_data.pop('class_enrollment', None)
        student = Student.objects.create(**validated_data)

        if class_enrollment_data:
            class_id = class_enrollment_data.get('class_id')
            academic_year = class_enrollment_data.get('academic_year')
            # Ensure to use `class_enrolled` instead of `class_id`
            ClassEnrollment.objects.create(student=student, class_enrolled_id=class_id, academic_year=academic_year)

        return student


class StudentParentRelationSerializer(serializers.ModelSerializer):
    student = UserSerializer()
    parent = UserSerializer()

    class Meta:
        model = StudentParentRelation
        fields = ['id', 'student', 'parent']


class SimpleStudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['id', 'name']


class SubjectSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    campus = CampusSerializer(read_only=True)
    class_name = serializers.CharField(source='class_id.name', read_only=True)  # Add the class name

    class Meta:
        model = Subject
        fields = ['id', 'name', 'class_id', 'class_name', 'school', 'campus', 'created_at', 'updated_at']


class TeacherLevelClassSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    campus = CampusSerializer(read_only=True)
    class_id = serializers.IntegerField(source='class_id.id', read_only=True)  # Ensure class_id is always included
    class_name = serializers.CharField(source='class_id.name', read_only=True)  # Ensure class name is always included
    subjects_taught = serializers.PrimaryKeyRelatedField(
        queryset=Subject.objects.all(),
        many=True,
        write_only=True
    )
    subjects_taught_details = SubjectSerializer(source='subjects_taught', many=True, read_only=True)

    teacher_name = serializers.CharField(source='teacher.username', read_only=True)

    class Meta:
        model = TeacherLevelClass
        fields = ['id', 'teacher', 'teacher_name', 'class_id', 'class_name', 'subjects_taught', 'subjects_taught_details', 'is_main_teacher', 'school', 'campus', 'created_at', 'updated_at']

    def create(self, validated_data):
        subjects = validated_data.pop('subjects_taught')
        teacher_level_class = TeacherLevelClass.objects.create(**validated_data)
        teacher_level_class.subjects_taught.set(subjects)
        return teacher_level_class

    def update(self, instance, validated_data):
        subjects = validated_data.pop('subjects_taught', None)
        instance.class_id = validated_data.get('class_id', instance.class_id)
        instance.save()

        if subjects is not None:
            instance.subjects_taught.set(subjects)
        return instance


class TeacherAssignmentHistorySerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    campus = CampusSerializer(read_only=True)
    subjects_taught_details = SubjectSerializer(source='subjects_taught', many=True, read_only=True)
    teacher_name = serializers.CharField(source='teacher.username', read_only=True)
    class_name = serializers.CharField(source='class_id.name', read_only=True)

    class Meta:
        model = TeacherAssignmentHistory
        fields = ['id', 'teacher_name', 'class_name', 'subjects_taught_details', 'unassigned_at', 'school', 'campus']



class AssessmentSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    campus = CampusSerializer(read_only=True)
    student_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    teacher_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    assessment_name_display = serializers.SerializerMethodField()
    term_name = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = [
            'id', 'topic', 'assessment_type', 'term_id', 'term_name', 'total_marks', 
            'obtained_marks', 'teacher_id', 'teacher_name', 'subject_id', 
            'subject_name', 'date', 'student_id', 'student_name', 
            'class_id', 'class_name', 'assessment_name_id', 'assessment_name_display'
            'comments', 'school', 'campus', 'created_at', 'updated_at'
        ]

    def get_student_name(self, obj):
        student = obj.student  # Changed from student_id to student (direct FK)
        return student.username if student else ''

    def get_class_name(self, obj):
        class_obj = obj.class_id
        return class_obj.name if class_obj else ''

    def get_teacher_name(self, obj):
        teacher = obj.teacher
        return teacher.username if teacher else ''

    def get_subject_name(self, obj):
        subject = obj.subject
        return subject.name if subject else ''
    
    def get_assessment_name_display(self, obj):
        assessment_name = obj.assessment_name
        return assessment_name.name if assessment_name else ''
    
    def get_term_name(self, obj):
        term = obj.term
        return term.name if term else ''


class SubjectPerformanceSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    campus = CampusSerializer(read_only=True)
    student_name = serializers.SerializerMethodField()
    subject_name = serializers.SerializerMethodField()
    class_name = serializers.SerializerMethodField()
    academic_year_display = serializers.SerializerMethodField()  # Renamed for clarity
    term_name = serializers.SerializerMethodField()

    class Meta:
        model = SubjectPerformance
        fields = [
            'student', 'student_name',           # Student ID and name
            'subject', 'subject_name',           # Subject ID and name
            'class_id', 'class_name',            # Class ID and name
            'academic_year', 'academic_year_display',
            'term_id', 'term_name',              # Term ID and name
            'average_score', 'school', 'campus'
        ]

    def get_student_name(self, obj):
        student = obj.student
        return student.username if student else ''  # Assuming username; adjust if name exists

    def get_subject_name(self, obj):
        subject = obj.subject
        return subject.name if subject else ''

    def get_class_name(self, obj):
        class_obj = obj.class_id
        return class_obj.name if class_obj else ''

    def get_academic_year_display(self, obj):
        academic_year = obj.academic_year
        return f"{academic_year.start_year}-{academic_year.end_year}" if academic_year else ''

    def get_term_name(self, obj):
        term = obj.term_id
        return term.name if term else ''


class PromoteStudentsSerializer(serializers.Serializer):
    student_ids = serializers.ListField(
        child=serializers.IntegerField()
    )
    new_class_id = serializers.IntegerField()
    academic_year = serializers.CharField(max_length=20)

    def validate_new_class_id(self, value):
        if not Class.objects.filter(id=value).exists():
            raise serializers.ValidationError("Class does not exist")
        return value

    def promote_students(self):
        student_ids = self.validated_data['student_ids']
        new_class_id = self.validated_data['new_class_id']
        academic_year = self.validated_data['academic_year']
        new_class = Class.objects.get(id=new_class_id)

        promoted_students = []
        for student_id in student_ids:
            try:
                student = Student.objects.get(id=student_id)
                ClassEnrollment.objects.create(student=student, class_id=new_class, academic_year=academic_year)
                student.class_id = new_class
                student.save()
                promoted_students.append(student)
            except Student.DoesNotExist:
                continue
        return {'status': 'success', 'promoted_students': [student.id for student in promoted_students]}


class TopicPerformanceSerializer(serializers.Serializer):
    topic = serializers.CharField()
    average_score = serializers.DecimalField(max_digits=5, decimal_places=2)
    assessment_type = serializers.CharField()
    semester = serializers.CharField()
    school = SchoolSerializer(read_only=True)
    campus = CampusSerializer(read_only=True)


class ProcessedMarksSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    campus = CampusSerializer(read_only=True)
    student = UserSerializer(read_only=True)  # Simplified student serializer
    class_ = ClassSerializer(read_only=True)  # Proper reference to the Class model using ClassSerializer

    class Meta:
        model = ProcessedMarks
        fields = ['student', 'class_', 'semester', 'total_score', 'status', 'subject_data', 'position', 'school', 'campus' 'created_at']


class TimeTableSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    campus = CampusSerializer(read_only=True)
    subject = SubjectSerializer(read_only=True)  # Include subject details
    teacher = UserSerializer(read_only=True)  # Include teacher details

    class Meta:
        model = TimeTable
        fields = ['id', 'class_id', 'subject', 'teacher', 'day', 'start_time', 'end_time', 'school', 'campus', 'created_at', 'updated_at']

        
class AssessmentNameSerializer(serializers.ModelSerializer):
    school = SchoolSerializer(read_only=True)
    campus = CampusSerializer(read_only=True)
    class Meta:
        model = AssessmentName
        fields = ['id', 'name', 'class_id', 'subject', 'teacher', 'created_at', 'school', 'campus', 'updated_at']
        read_only_fields = ['teacher', 'created_at', 'updated_at']  # Teacher set by view, timestamps auto-managed