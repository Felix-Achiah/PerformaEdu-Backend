from django.db import transaction
import logging
from urllib.parse import unquote
from django.db.models import Avg, Sum, Count, FloatField, ExpressionWrapper, F, Q
from django.db.models.functions import Round
from decimal import Decimal, InvalidOperation
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework import status, permissions, generics
from rest_framework.mixins import (
    ListModelMixin, 
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin
)

from .assign_grade import assign_grade
from .consolidate_subject_data import consolidate_subject_data
from .get_position_suffix import get_position_suffix
from user_auth.permissions import IsParent, IsHeadmaster, IsTeacher, IsAdminOrAssignedTeacher, IsAssignedTeacher, IsTeacherOrAdmin, IsAdmin, IsRegisteredInSchoolOrCampus, IsTeacherOrAdminInSchoolOrCampus
from .models import Class, Subject, TeacherLevelClass, Student, ClassEnrollment, HistoricalClassEnrollment, Assessment, StudentParentRelation, SubjectPerformance, ProcessedMarks, TimeTable, AssessmentName, Level, Terms
from user_auth.models import User, Role
from user_auth.serializers import UserSerializer
from .serializers import ClassSerializer, SubjectSerializer, TeacherLevelClassSerializer, StudentSerializer, AssessmentSerializer, PromoteStudentsSerializer, ClassEnrollmentSerializer, SubjectPerformanceSerializer, TopicPerformanceSerializer, ProcessedMarksSerializer, StudentParentRelationSerializer, TimeTableSerializer, AssessmentNameSerializer, LevelSerializer, TermsSerializer
from administrator.models import AcademicYear
from school.models import School, Campus

logger = logging.getLogger(__name__)

'''CRUD endpoints for Class'''
# Create endpoint
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsTeacherOrAdminInSchoolOrCampus])
def create_class(request):
    # Check if the request data is a single class or a list of classes
    is_many = isinstance(request.data, list)
    
    # Serialize the data accordingly
    serializer = ClassSerializer(data=request.data, many=is_many)
    
    if serializer.is_valid():
        serializer.save()
        if is_many:
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.data[0], status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Retrieve all classes created
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus | IsTeacherOrAdminInSchoolOrCampus])
def get_all_classes(request):
    if request.method == 'GET':
        level_type = request.query_params.get('level')  # Assuming the level type is passed as a query parameter

        if level_type:
            # Filter classes based on the level type
            classes = Class.objects.filter(level_type=level_type)
            serializer = ClassSerializer(classes, many=True)
            return Response(serializer.data)
        else:
            return Response({'error': 'Please provide a level_type parameter'}, status=status.HTTP_400_BAD_REQUEST)

# Retrieve a specific class endpoint
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def retrieve_class(request, class_id):
    try:
        class_obj = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({'error': 'Class not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ClassSerializer(class_obj)
    return Response(serializer.data)

# Update endpoint
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def update_class(request, class_id):
    try:
        print('id', class_id)
        class_obj = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({'error': 'Class not found'}, status=status.HTTP_404_NOT_FOUND)

    serializer = ClassSerializer(class_obj, data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Delete endpoint
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def delete_class(request, class_id):
    try:
        print('id', class_id)
        class_obj = Class.objects.get(id=class_id)
        print(class_obj)
    except Class.DoesNotExist:
        return Response({'error': 'Class not found'}, status=status.HTTP_404_NOT_FOUND)

    class_obj.delete()
    return Response({'message': 'Class deleted successfully'}, status=status.HTTP_204_NO_CONTENT)


'''CRUD endpoints for Subject'''
# List all subjects
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def subject_list(request):
    if request.method == 'GET':
        class_id = request.query_params.get('class_id')  # Assuming the level type is passed as a query parameter

        print(class_id)
        if class_id:
            # Filter classes based on the level type
            subjects = Subject.objects.filter(class_id=class_id)
            serializer = SubjectSerializer(subjects, many=True)
            return Response(serializer.data)
        else:
            return Response({'error': 'Please provide a class_id parameter'}, status=status.HTTP_400_BAD_REQUEST)

# Create a new subject
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def create_subject(request):
    names = request.data.get('name', [])  # Get the list of names from request data
    class_id = request.data.get('class_id', None)  # Get the class_id
    
    subjects_created = []
    
    # Loop through the list of names
    for name in names:
        # Create a Subject object for each name
        subject_data = {'name': name, 'class_id': class_id}
        serializer = SubjectSerializer(data=subject_data)
        
        if serializer.is_valid():
            serializer.save()
            subjects_created.append(serializer.data)
        else:
            # If the serializer is not valid, return the error response
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    # Return the list of created subjects
    return Response(subjects_created, status=status.HTTP_201_CREATED)

# Retrieve details of a subject
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def subject_detail(request, subject_id):
    subject = Subject.objects.get(id=subject_id)
    serializer = SubjectSerializer(subject)
    return Response(serializer.data)


# Update details of a subject
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def update_subject(request, subject_id):
    print(request.data)
    subject = Subject.objects.get(id=subject_id)
    serializer = SubjectSerializer(subject, data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Delete a subject
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def delete_subject(request, subject_id):
    subject = Subject.objects.get(id=subject_id)
    subject.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)


# Teachers register subjects to be taught in a class.
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def register_teacher_subjects(request):
    if request.method == 'POST':
        print(request.data)
        existing_subjects = TeacherLevelClass.objects.filter(
            teacher=request.user, class_id__id=request.data['class_id']
        )
        existing_subject_ids = set(
            existing_subjects.values_list('subjects_taught', flat=True)
        )
        new_subject_ids = set(request.data['subjects_taught'])

        duplicate_subject_ids = existing_subject_ids.intersection(new_subject_ids)
        if duplicate_subject_ids:
            duplicate_subjects = Subject.objects.filter(id__in=duplicate_subject_ids)
            duplicate_subject_names = ', '.join([subject.name for subject in duplicate_subjects])
            return Response(
                {'error': f'The following subjects are already registered: {duplicate_subject_names}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = TeacherLevelClassSerializer(data=request.data, context={'request': request})

        if serializer.is_valid():
            if existing_subjects.exists():
                # Update existing TeacherLevelClass object
                teacher_level_class = existing_subjects.first()
                serializer = TeacherLevelClassSerializer(
                    teacher_level_class, data=request.data, partial=True, context={'request': request}
                )
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_200_OK) # Adjust status code to 200 (update)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            else:
                # Create a new TeacherLevelClass object
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
# Update Subjects registered to a Teacher
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def update_teacher_subjects(request, class_id):
    try:
        teacher_level_class = TeacherLevelClass.objects.get(teacher=request.user, class_id=class_id)
    except TeacherLevelClass.DoesNotExist:
        return Response({'error': 'TeacherLevelClass not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = TeacherLevelClassSerializer(
        teacher_level_class, data=request.data, partial=True, context={'request': request}
    )
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# Retrieve Subjects registered to a Teacher
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_teacher_registered_subjects(request, class_id):
    try:
        teacher_id = int(request.user.id)
        teacher_level_class = TeacherLevelClass.objects.get(teacher_id=teacher_id, class_id=class_id)
    except TeacherLevelClass.DoesNotExist:
        return Response({'subjects_taught_details': []}, status=status.HTTP_200_OK)

    serializer = TeacherLevelClassSerializer(teacher_level_class)
    return Response([serializer.data], status=status.HTTP_200_OK)


''' PROMOTE STUDENTS OR A STUDENT TO A DIFFERENT CLASS'''

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def promote_students(request):
    student_ids = request.data.get('student_ids', [])
    new_class_id = request.data.get('new_class_id')
    academic_year = request.data.get('academic_year')

    if not student_ids or not new_class_id or not academic_year:
        return Response({"error": "Missing required parameters."}, status=status.HTTP_400_BAD_REQUEST)
    
    new_class = get_object_or_404(Class, id=new_class_id)

    promoted_students = []

    try:
        for student_id in student_ids:
            student = get_object_or_404(Student, id=student_id)
            current_class_enrollment = ClassEnrollment.objects.filter(student=student).first()
            
            # Move current enrollment to historical
            if current_class_enrollment:
                HistoricalClassEnrollment.objects.create(
                    student=student,
                    class_enrolled=current_class_enrollment.class_id,
                    academic_year=current_class_enrollment.academic_year
                )
                current_class_enrollment.delete()
            
            # Enroll student in new class
            new_enrollment = ClassEnrollment.objects.create(
                student=student,
                class_id=new_class,
                academic_year=academic_year,
                status='promoted'
            )
            promoted_students.append({
                'student_id': student.id,
                'student_name': student.name,
                'new_class_id': new_class.id,
                'new_class_name': new_class.name,
                'enrollment_date': new_enrollment.academic_year
            })

        return Response({
            'message': 'Students promoted successfully',
            'promoted_students': promoted_students
        }, status=status.HTTP_200_OK)


    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Repeat Students or Student in a class and in a different academic year
@api_view(['POST'])
def repeat_students(request):
    student_ids = request.data.get('student_ids', [])
    class_id = request.data.get('class_id')
    academic_year = request.data.get('academic_year')

    if not student_ids or not class_id or not academic_year:
        return Response({"error": "Missing required fields"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        class_instance = Class.objects.get(id=class_id)
        students = Student.objects.filter(id__in=student_ids)

        for student in students:
            current_class_enrollment = ClassEnrollment.objects.filter(student=student).first()

            # Move current enrollment to historical
            if current_class_enrollment:
                HistoricalClassEnrollment.objects.create(
                    student=student,
                    class_enrolled=current_class_enrollment.class_id,
                    academic_year=current_class_enrollment.academic_year
                )
                current_class_enrollment.delete()
            enroll_repeated_student = ClassEnrollment.objects.create(
                student=student,
                class_id=class_instance,
                academic_year=academic_year,
                status='repeated'
            )

        return Response({"message": "Students repeated successfully"}, status=status.HTTP_200_OK)

    except Class.DoesNotExist:
        return Response({"error": "Class not found"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def get_promoted_existing_repeated_students(request, class_id):
    try:
        new_class = get_object_or_404(Class, id=class_id)

        promoted_enrollments = ClassEnrollment.objects.filter(class_id=new_class, status='promoted').select_related('student')
        existing_enrollments = ClassEnrollment.objects.filter(class_id=new_class, status='existing').select_related('student')
        repeated_enrollments = ClassEnrollment.objects.filter(class_id=new_class, status='repeated').select_related('student')
        
        promoted_students_data = []
        for enrollment in promoted_enrollments:
            historical_enrollment = HistoricalClassEnrollment.objects.filter(student=enrollment.student).order_by('-id').first()
            previous_class_name = historical_enrollment.class_enrolled.name if historical_enrollment else None
            student_data = StudentSerializer(enrollment.student).data
            student_data['previous_class_name'] = previous_class_name
            promoted_students_data.append(student_data)

        existing_students_data = StudentSerializer([enrollment.student for enrollment in existing_enrollments], many=True).data
        
        repeated_students_data = []
        for enrollment in repeated_enrollments:
            historical_enrollment = HistoricalClassEnrollment.objects.filter(student=enrollment.student).order_by('-id').first()
            previous_class_name = historical_enrollment.class_enrolled.name if historical_enrollment else None
            student_data = StudentSerializer(enrollment.student).data
            student_data['previous_class_name'] = previous_class_name
            repeated_students_data.append(student_data)

        return Response({
            "promoted_students": promoted_students_data,
            "existing_students": existing_students_data,
            "repeated_students": repeated_students_data
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def merge_promoted_repeated_students(request):
    student_ids = request.data.get('student_ids', [])

    if not student_ids:
        return Response({"error": "Missing required parameters."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        for student_id in student_ids:
            student = get_object_or_404(Student, id=student_id)
            class_enrollments = ClassEnrollment.objects.filter(student=student, status__in=['promoted', 'repeated'])

            for enrollment in class_enrollments:
                enrollment.status = 'existing'
                enrollment.save()

        return Response({"message": "Students merged successfully."}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsParent | IsTeacher | IsHeadmaster])
def get_students_by_class_id(request):
    class_id = request.query_params.get('class_id')
    if not class_id:
        return Response({'error': 'Class ID parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        student_role = Role.objects.get(name='Student')
        enrollments = ClassEnrollment.objects.filter(
            class_id=class_id,
            status='existing',
            student__roles=student_role
        ).select_related('student', 'class_id', 'academic_year')

        logger.info(f"Enrollments found: {enrollments.count()}")
        serializer = ClassEnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    except Role.DoesNotExist:
        return Response({'error': "Role 'Student' does not exist"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except ClassEnrollment.DoesNotExist:
        return Response({'error': f"No students found for class_id {class_id} with status 'existing'"}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Update a specific student
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def update_student(request, student_id):
    try:
        student = User.objects.get(id=student_id)
    except User.DoesNotExist:
        return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Update student data
    student_serializer = UserSerializer(student, data=request.data, partial=True)
    if not student_serializer.is_valid():
        return Response(student_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    student_serializer.save()

    # Update class enrollment data if provided
    if 'class_enrollment' in request.data:
        enrollment_data = request.data.get('class_enrollment', {})
        try:
            # Assuming only one 'existing' enrollment per student at a time
            enrollment = ClassEnrollment.objects.get(student=student, status='existing')
            class_enrollment_serializer = ClassEnrollmentSerializer(enrollment, data=enrollment_data, partial=True)
            if class_enrollment_serializer.is_valid():
                # Handle class_id and academic_year lookups
                if 'class_id' in enrollment_data:
                    class_id = enrollment_data['class_id']
                    enrollment.class_id = Class.objects.get(id=class_id)
                if 'academic_year' in enrollment_data:
                    academic_year = enrollment_data['academic_year']
                    enrollment.academic_year = AcademicYear.objects.get(start_year=academic_year)
                if 'status' in enrollment_data:
                    enrollment.status = enrollment_data['status']
                enrollment.save()
                logger.info(f"Updated enrollment for student {student_id}: {enrollment_data}")
            else:
                return Response(class_enrollment_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except ClassEnrollment.DoesNotExist:
            # Create new enrollment if none exists
            class_id = enrollment_data.get('class_id')
            academic_year = enrollment_data.get('academic_year')
            status = enrollment_data.get('status', 'existing')
            if class_id and academic_year:
                new_enrollment = ClassEnrollment(
                    student=student,
                    class_id=Class.objects.get(id=class_id),
                    academic_year=AcademicYear.objects.get(start_year=academic_year),
                    status=status
                )
                new_enrollment.save()
                logger.info(f"Created new enrollment for student {student_id}: {enrollment_data}")
            else:
                return Response({'error': 'class_id and academic_year are required for new enrollment'}, status=status.HTTP_400_BAD_REQUEST)
        except (Class.DoesNotExist, AcademicYear.DoesNotExist) as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    return Response(student_serializer.data, status=status.HTTP_200_OK)


# Get a specific student
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def get_student(request, student_id):
    print(student_id)
    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = StudentSerializer(student)
    return Response(serializer.data)

# Delete a specific student
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def delete_student(request, student_id):
    try:
        student = Student.objects.get(id=student_id)
    except Student.DoesNotExist:
        return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

    student.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)



'''STUDENT ASSESSTMENT ENDPOINTS'''

# Create student assesstment 
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def create_assessments(request):
    if request.method == 'POST':
        teacher_id = int(request.user.id)
        teacher = User.objects.get(id=teacher_id)

        assessments_data = request.data.get('assessments', [])  # Get the list of assessment data from the request

        created_assessments = []
        errors = []

        for data in assessments_data:
            # Extract class, subject, and student marks data
            class_id = data.pop('class_id')
            subject_id = data.pop('subject')
            students_data = data.pop('student_marks', [])
            
            subject = Subject.objects.get(pk=subject_id)
            class_obj = Class.objects.get(pk=class_id)
            
            # Check if the teacher is assigned to teach the subject in the specified class
            teacher_level_class = TeacherLevelClass.objects.filter(
                teacher=teacher, class_id=class_obj, subjects_taught=subject
            ).first()
            if not teacher_level_class:
                errors.append({'error': f'Teacher is not assigned to teach subject with ID {subject_id} in class with ID {class_id}'})
                continue

            for student_data in students_data:
                student_id = student_data.get('id')
                obtained_marks = student_data.get('obtained_marks')

                try:
                    # Validate and convert total_marks and obtained_marks to Decimal
                    total_marks = data.get('total_marks')
                    if total_marks is not None:
                        try:
                            total_marks = Decimal(total_marks)
                        except InvalidOperation:
                            errors.append({'detail': f"Invalid total_marks value: {total_marks}"})
                            continue
                    else:
                        total_marks = Decimal('0.00')

                    # Handle empty string for obtained_marks
                    if obtained_marks is None or obtained_marks == "":
                        obtained_marks = Decimal('0.00')
                    else:
                        try:
                            obtained_marks = Decimal(obtained_marks)
                        except InvalidOperation:
                            errors.append({'detail': f"Invalid obtained_marks value: {obtained_marks}"})
                            continue

                    student = Student.objects.get(pk=student_id)
                    assessment_data = {
                        'student_id': student,
                        'class_id': class_obj,
                        'teacher': teacher,
                        'subject': subject,
                        'total_marks': total_marks,
                        'topic': data.get('topic'),
                        'assessment_type': data.get('assessment_type'),
                        'semester': data.get('semester'),
                        'date': data.get('date'),
                        'obtained_marks': obtained_marks
                    }
                    assessment_instance = Assessment.objects.create(**assessment_data)
                    created_assessments.append(assessment_instance)
                except Student.DoesNotExist:
                    errors.append({'detail': f"Student with ID {student_id} does not exist."})
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Serialize the created assessment instances
            serializer = AssessmentSerializer(created_assessments, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsTeacher | IsParent | IsHeadmaster])
def fetch_historical_assessment_data(request):
    try:
        # Extract parameters from request data
        student_id = request.data.get('student_id')
        class_id = request.data.get('class_id')
        academic_year = request.data.get('academic_year')
        assessment_type = request.data.get('assessment_type')
        subject_id = request.data.get('subject_id')
        semester = request.data.get('semester')

        # Fetch student and class instances for better messages
        student = Student.objects.get(id=student_id)
        class_instance = Class.objects.get(id=class_id)

        # Check if student was enrolled (current or historical) for the given academic year
        current_enrollment = ClassEnrollment.objects.filter(
            student=student,
            class_id=class_instance,
            academic_year=academic_year,
        ).exists()

        historical_enrollment = HistoricalClassEnrollment.objects.filter(
            student=student,
            class_enrolled=class_instance,
            academic_year=academic_year,
        ).exists()

        if not current_enrollment and not historical_enrollment:
            message = f"Sorry, {student.name} didn't enroll in the {class_instance.name} class in the {academic_year} academic year."
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)
        
        # Filter assessments based on parameters
        assessments = Assessment.objects.filter(
            student_id=student_id,
            class_id=class_id,
            subject=subject_id,
            assessment_type=assessment_type,
        )

        # Check if semester filter is applicable
        if assessment_type in ['Exercise', 'Assignment'] and semester:
            assessments = assessments.filter(semester=semester)
        elif assessment_type not in ['Exercise', 'Assignment', 'Final Exams', 'Mid Term Exams']:
            assessments = assessments.exclude(semester__in=['1st Semester', '2nd Semester'])

        # Serialize queryset into JSON
        serializer = AssessmentSerializer(assessments, many=True)
        
        return Response({'assessments': serializer.data}, status=status.HTTP_200_OK)
    
    except Student.DoesNotExist:
        return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Class.DoesNotExist:
        return Response({'error': 'Class not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def get_student_assessments(request, student_id, semester, subject_id, assessment_type):
    try:
        # Retrieve assessments based on provided filters
        assessments = Assessment.objects.filter(
            student_id=student_id,
            semester=semester,
            subject_id=subject_id,
            assessment_type=assessment_type
        )
        
        # Serialize the assessments
        serializer = AssessmentSerializer(assessments, many=True)
        print(serializer.data)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    

# Get Student Mid Term or Final Exam assessment
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def get_student_exams_assessments(request, student_id, subject_id, assessment_type):
    try:
        # Retrieve assessments based on provided filters
        assessments = Assessment.objects.filter(
            student_id=student_id,
            subject_id=subject_id,
            assessment_type=assessment_type
        )
        
        # Serialize the assessments
        serializer = AssessmentSerializer(assessments, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def get_student_assessment(request, student_id, assessment_id):
    try:
        # Retrieve the specific assessment based on student_id and assessment_id
        assessment = Assessment.objects.get(
            student_id=student_id,
            id=assessment_id
        )
        
        # Serialize the assessment
        serializer = AssessmentSerializer(assessment)
        return Response(serializer.data)
    except Assessment.DoesNotExist:
        return Response({'error': 'Assessment not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    

# Update students' assessment(s)
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def update_assessments(request):
    if request.method == 'PUT':
        teacher_id = request.user.id
        teacher = User.objects.get(id=teacher_id)

        assessments_data = request.data.get('assessments', [])  # Get the list of assessment data from the request

        user = request.user  # Get the authenticated user (teacher)
        
        updated_assessments = []
        errors = []
        
        for data in assessments_data:
            class_id = data.pop('class_id', None)
            subject_id = data.pop('subject', None)
            student = data.pop('student', None)
            if subject_id is None:
                errors.append({'detail': 'Subject ID is required.'})
                continue

            # Retrieve the subject based on the subject_id
            try:
                subject = Subject.objects.get(pk=subject_id)
            except Subject.DoesNotExist:
                errors.append({'detail': f'Subject with ID {subject_id} does not exist.'})
                continue

            class_id = Class.objects.get(pk=class_id)

            assessment_id = data.pop('assessment_id', None)
            if assessment_id is None:
                errors.append({'detail': 'Assessment ID is required.'})
                continue
            
            # Check if the assessment exists
            try:
                assessment_instance = Assessment.objects.get(pk=assessment_id)
            except Assessment.DoesNotExist:
                errors.append({'detail': f'Assessment with ID {assessment_id} does not exist.'})
                continue

            # Validate class_id, student_id, and assessment_id
            try:
                class_instance = Class.objects.get(pk=class_id.pk)
                print(class_instance.pk)
                student_instance = Student.objects.get(pk=student)
                print(student_instance.pk)
                assessment_instance = Assessment.objects.get(pk=assessment_id)
            except (Class.DoesNotExist, Student.DoesNotExist, Assessment.DoesNotExist) as e:
                errors.append({'detail': str(e)})
                continue

            # Check if the teacher is assigned to teach the subject in the specified class
            teacher_level_class = TeacherLevelClass.objects.filter(
                teacher=user, class_id=assessment_instance.class_id, subjects_taught=assessment_instance.subject
            ).first()
            if not teacher_level_class:
                errors.append({'detail': f'Teacher is not assigned to teach subject with ID {assessment_instance.subject.id} in class with ID {assessment_instance.class_id}'})
                continue

            obtained_marks = data.pop('obtained_marks', None)

            if student is None:
                errors.append({'detail': 'Student data are required.'})
                continue
            
            print(f'{student_instance.pk}/n{teacher.pk}/n{subject.pk}/n{class_instance.pk}')
            # Update assessment data
            data['obtained_marks'] = obtained_marks
            data['student'] = student_instance.pk
            data['teacher'] = teacher.pk
            data['subject'] = subject.pk  # Keep the subject unchanged
            data['class_id'] = class_instance.pk  # Keep the class unchanged

            # Update the assessment instance
            serializer = AssessmentSerializer(assessment_instance, data=data, partial=True)
            if serializer.is_valid():
                updated_instance = serializer.save()
                updated_assessments.append(updated_instance)
            else:
                errors.append(serializer.errors)
        
        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Serialize the updated assessment instances
            serializer = AssessmentSerializer(updated_assessments, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
    

# Delete a student's assessment
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def delete_assessment(request, student_id, assessment_id):
    print(f"Requested URL: {request.path}")  # Print the full requested URL
    print(f"Student ID: {student_id}")  # Print the captured student ID
    print(f"Assessment ID: {assessment_id}")  # Print the captured assessment ID
    try:
        # Retrieve the student object
        student = Student.objects.get(pk=student_id)
    except Student.DoesNotExist:
        # If the student does not exist, return a 404 Not Found response
        return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        # Retrieve the assessment object related to the student
        assessment = Assessment.objects.get(pk=assessment_id, student_id=student)
    except Assessment.DoesNotExist:
        # If the assessment does not exist for the student, return a 404 Not Found response
        return Response({'detail': 'Assessment not found for the student.'}, status=status.HTTP_404_NOT_FOUND)

    # Delete the assessment
    assessment.delete()

    # Return a success message
    return Response({'detail': 'Assessment deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)


# Fetch Classes a Teacher teaches subject(s) in
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def get_teacher_classes(request):
    try:
        teacher_id = request.user.id
        teacher_classes = TeacherLevelClass.objects.filter(teacher_id=teacher_id)
        serializer = TeacherLevelClassSerializer(teacher_classes, many=True)
        return Response(serializer.data)
    except TeacherLevelClass.DoesNotExist:
        return Response(status=status.HTTP_404_NOT_FOUND)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def filter_topics(request):
  """
  View to handle topic filtering based on search term.
  """
  topic = request.GET.get('topic', '')
  filters = {}

  if topic:
    filters['topic__icontains'] = topic.lower()  # Case-insensitive # Use distinct() for unique topics
    topics = Assessment.objects.filter(**filters).distinct('topic').values_list('topic', flat=True)
  else:
    topics = []  # Return empty list if no topic provided

  return JsonResponse({'topics': list(topics)})   # Return data as JSON


# Assign Students to Parents
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsParent])
def assign_students_to_parents(request):
    user = request.user
    if user.user_type != 'Parent':
        return Response({'error': 'Only parents can assign students'}, status=status.HTTP_403_FORBIDDEN)

    student_ids = request.data.get('student_ids')
    if not student_ids:
        return Response({'error': 'No students selected'}, status=status.HTTP_400_BAD_REQUEST)

    for student_id in student_ids:
        student = get_object_or_404(Student, id=student_id)
        if StudentParentRelation.objects.filter(student=student).count() >= 2:
            return Response({'error': f'Student {student.name} is already assigned to two parents'}, status=status.HTTP_400_BAD_REQUEST)

        # Check if the relation already exists for this parent
        if StudentParentRelation.objects.filter(student=student, parent=user).exists():
            return Response({'error': f'Student {student.name} is already assigned to you'}, status=status.HTTP_400_BAD_REQUEST)

        StudentParentRelation.objects.get_or_create(student=student, parent=user)

    return Response({'message': 'Students assigned successfully'}, status=status.HTTP_200_OK)


# Fetch students assigned to a Parent as children
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsParent])
def get_students_assigned_to_parent(request):
    user = request.user
    if user.user_type != 'Parent':
        return Response({'error': 'Only parents can retrieve assigned students'}, status=status.HTTP_403_FORBIDDEN)

    assigned_students = StudentParentRelation.objects.filter(parent=user).select_related('student')
    students = [relation.student for relation in assigned_students]
    serializer = StudentSerializer(students, many=True)

    return Response(serializer.data, status=status.HTTP_200_OK)

# Get Student and Parent info
class StudentParentRelationView(APIView):

    def get(self, request, student_id=None):
        try:
            # Fetch the relation data based on the student ID
            if student_id:
                student_relations = StudentParentRelation.objects.filter(student_id=student_id)
            else:
                return Response({"error": "Student ID not provided"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Serialize the data
            serializer = StudentParentRelationSerializer(student_relations, many=True)
            
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except StudentParentRelation.DoesNotExist:
            return Response({"error": "Student relations not found"}, status=status.HTTP_404_NOT_FOUND)
        
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated, IsParent])
def delete_child(request, student_id):
    try:
        # Ensure the user is a parent
        if request.user.user_type != 'Parent':
            return Response({'error': 'You do not have permission to perform this action.'}, status=status.HTTP_403_FORBIDDEN)

        # Get the StudentParentRelation object
        relation = get_object_or_404(StudentParentRelation, student_id=student_id, parent=request.user)

        # Delete the relationship
        relation.delete()

        return Response({'message': 'Student successfully removed from your children list.'}, status=status.HTTP_204_NO_CONTENT)
    
    except StudentParentRelation.DoesNotExist:
        return Response({'error': 'The specified student is not listed under your children.'}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class ChildrenPerformanceView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsParent]

    def get(self, request, class_id, student_id, semester, assessment_type, subject_id):
        try:
            student = Student.objects.get(id=student_id)
            class_instance = Class.objects.get(id=class_id)

            assessments = Assessment.objects.filter(
                student_id=student_id,
                class_id=class_id,
                subject=subject_id,
                assessment_type=assessment_type,
            )

            if assessment_type in ['Exercise', 'Assignment'] and semester:
                assessments = assessments.filter(semester=semester)
            elif assessment_type not in ['Exercise', 'Assignment', 'Final Exams', 'Mid Term Exams']:
                assessments = assessments.exclude(semester__in=['1st Semester', '2nd Semester'])

            serializer = AssessmentSerializer(assessments, many=True)
            return Response({'assessments': serializer.data}, status=status.HTTP_200_OK)

        except Student.DoesNotExist:
            return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Class.DoesNotExist:
            return Response({'error': 'Class not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request):
        try:
            # Extract parameters from request data
            student_id = request.data.get('student_id')
            class_id = request.data.get('class_id')
            assessment_type = request.data.get('assessment_type')
            subject_id = request.data.get('subject_id')
            semester = request.data.get('semester')

            # Perform the semester and assessment type check to filter data
            if assessment_type in ['Exercise', 'Assignment'] and semester:
                assessments = Assessment.objects.filter(
                    student_id=student_id,
                    class_id=class_id,
                    subject=subject_id,
                    assessment_type=assessment_type,
                    semester=semester
                )
            elif assessment_type not in ['Exercise', 'Assignment', 'Final Exams', 'Mid Term Exams']:
                assessments = Assessment.objects.filter(
                    student_id=student_id,
                    class_id=class_id,
                    subject=subject_id,
                    assessment_type=assessment_type
                ).exclude(
                    semester__in=['1st Semester', '2nd Semester']
                )
            else:
                assessments = Assessment.objects.filter(
                    student_id=student_id,
                    class_id=class_id,
                    subject=subject_id,
                    assessment_type=assessment_type
                )

            # Serialize the filtered queryset into JSON
            serializer = AssessmentSerializer(assessments, many=True)
            return Response({'assessments': serializer.data}, status=status.HTTP_200_OK)

        except Student.DoesNotExist:
            return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Class.DoesNotExist:
            return Response({'error': 'Class not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class HistoricalSubjectPerformanceView(APIView):
    permission_classes = [permissions.IsAuthenticated | IsParent | IsTeacher | IsHeadmaster]

    def get(self, request, student_id):
        # Retrieve relevant assessments for the student
        assessments = Assessment.objects.filter(student_id=student_id)

        if not assessments.exists():
            return Response({"detail": "No assessments found for this student."}, status=status.HTTP_404_NOT_FOUND)

        # Retrieve academic years from ClassEnrollment and HistoricalClassEnrollment
        class_enrollments = ClassEnrollment.objects.filter(student_id=student_id).values(
            'class_id', 'academic_year', 'class_id__name'
        )

        historical_enrollments = HistoricalClassEnrollment.objects.filter(student_id=student_id).values(
            'class_enrolled', 'academic_year', 'class_enrolled__name'
        )

        # Calculate performance with rounded and scaled averages for subjects per class
        performances = assessments.annotate(
            scaled_score=Round((F('obtained_marks') / F('total_marks')) * 100, 2)
        ).values(
            'subject', 'subject__name', 'class_id'
        ).annotate(
            average_score=Round(Avg('scaled_score'), 2)
        )

        # Combine results with academic year and class names
        performance_data = []
        for entry in performances:
            class_data = next(
                (enrollment for enrollment in class_enrollments if enrollment['class_id'] == entry['class_id']),
                None
            ) or next(
                (enrollment for enrollment in historical_enrollments if enrollment['class_enrolled'] == entry['class_id']),
                None
            )
            if class_data:
                performance_data.append({
                    'student_id': student_id,
                    'subject_id': entry['subject'],
                    'subject_name': entry['subject__name'],
                    'class_id': entry['class_id'],
                    'academic_year': class_data['academic_year'],
                    'class_name': class_data.get('class_id__name') or class_data.get('class_enrolled__name'),
                    'average_score': entry['average_score'],
                })

        return Response(performance_data, status=status.HTTP_200_OK)


class HistoricalPerformanceView(APIView):
    permission_classes = [permissions.IsAuthenticated | IsParent | IsTeacher | IsHeadmaster]

    def get(self, request, student_id):
        # Retrieve all assessments for the student
        assessments = Assessment.objects.filter(student_id=student_id)

        if not assessments.exists():
            return Response({"detail": "No assessments found for this student."}, status=status.HTTP_404_NOT_FOUND)

        # Calculate average score for each subject per academic year and class
        performances = assessments.values(
            'subject', 'class_id', 'class_id__academic_year'
        ).annotate(
            semester_score=Avg('obtained_marks')
        ).values(
            'subject', 'class_id', 'class_id__academic_year'
        ).annotate(
            academic_year_average=Avg('semester_score')
        )

        # Convert to SubjectPerformance model and serialize the data
        performance_data = [
            SubjectPerformance(
                student_id=student_id,
                subject_id=entry['subject'],
                class_id_id=entry['class_id'],
                academic_year=entry['class_id__academic_year'],
                average_score=entry['academic_year_average'],
            )
            for entry in performances
        ]

        serializer = SubjectPerformanceSerializer(performance_data, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# Class view for calculating the average of topic assessment marks for both exercise and assignment.
class WeightedTopicPerformanceView(APIView):
    permission_classes = [permissions.IsAuthenticated | IsParent | IsTeacher | IsHeadmaster]

    def get(self, request, student_id, class_id, subject_id, semester):
        # Calculate counts and average marks for both exercises and assignments
        topic_performance = Assessment.objects.filter(
            student_id=student_id,
            class_id=class_id,
            subject_id=subject_id,
            semester=semester,
            assessment_type__in=['Exercise', 'Assignment']
        ).values('topic', 'assessment_type').annotate(
            count=Count('id'),
            average_marks=Avg('obtained_marks')
        )
        
        performance_data = {}

        # Organize the data by topic, calculating the weighted average
        for entry in topic_performance:
            topic = entry['topic']
            assessment_type = entry['assessment_type']
            count = entry['count']
            average_marks = entry['average_marks']

            if topic not in performance_data:
                performance_data[topic] = {
                    'exercise': {'count': 0, 'average': 0},
                    'assignment': {'count': 0, 'average': 0}
                }

            if assessment_type == 'Exercise':
                performance_data[topic]['exercise'] = {'count': count, 'average': average_marks}
            else:
                performance_data[topic]['assignment'] = {'count': count, 'average': average_marks}

        # Calculate weighted averages
        for topic, data in performance_data.items():
            exercise_count = data['exercise']['count']
            assignment_count = data['assignment']['count']
            
            total_count = exercise_count + assignment_count
            if total_count == 0:
                continue  # Skip if no data for this topic

            # Weights based on count
            exercise_weight = float(exercise_count) / total_count
            assignment_weight = float(assignment_count) / total_count

            # Convert average marks to float before multiplying
            weighted_exercise = float(data['exercise']['average']) * exercise_weight if data['exercise']['average'] else 0
            weighted_assignment = float(data['assignment']['average']) * assignment_weight if data['assignment']['average'] else 0

            data['weighted_exercise'] = round(weighted_exercise, 2)
            data['weighted_assignment'] = round(weighted_assignment, 2)

        # Convert performance_data to a list of dictionaries for the frontend
        response_data = [
            {
                'topic': topic,
                'exercise': data['weighted_exercise'],
                'assignment': data['weighted_assignment']
            }
            for topic, data in performance_data.items()
        ]

        return Response(response_data, status=status.HTTP_200_OK)


class TopicPerformanceByTypeView(APIView):
    permission_classes = [permissions.IsAuthenticated | IsParent | IsTeacher | IsHeadmaster]

    def get(self, request, student_id, class_id, subject_id, semester, assessment_type):
        # Step 1: Validate the assessment type
        if assessment_type not in ['Exercise', 'Assignment']:
            return Response({"error": "Invalid assessment type"}, status=status.HTTP_400_BAD_REQUEST)

        # Step 2: Filter assessments by student, class, subject, semester, and assessment type
        assessments = Assessment.objects.filter(
            student_id=student_id,
            class_id=class_id,
            subject_id=subject_id,
            semester=semester,
            assessment_type=assessment_type
        ).order_by('created_at')  # Add explicit ordering

        # Perform aggregation for the performance data
        performance_data = assessments.values('topic').annotate(
            count=Count('id'),
            total_marks=Sum('obtained_marks'),
            average_marks=Avg('obtained_marks')
        )

        # Fetch class, subject, and teacher details
        class_instance = Class.objects.get(id=class_id)
        subject_instance = Subject.objects.get(id=subject_id)
        teacher_instance = assessments.first().teacher if assessments.exists() else None

        performance_data_list = []
        total_assessments = 0
        total_weighted_marks = 0

        # Step 3: Calculate weighted averages
        for entry in performance_data:
            topic = entry['topic']
            count = entry['count']
            total_marks = entry['total_marks']
            average_marks = entry['average_marks']

            total_assessments += count
            total_weighted_marks += average_marks * count

            performance_data_list.append({
                'topic': topic,
                'count': count,
                'total_marks': total_marks,
                'average_marks': average_marks,
                'weighted_average': 0  # Placeholder for now
            })

        # Step 4: Compute the overall weighted average for accuracy
        overall_weighted_average = total_weighted_marks / total_assessments if total_assessments > 0 else 0

        # Step 5: Adjust individual topic averages for balanced insight
        for item in performance_data_list:
            item['weighted_average'] = (item['average_marks'] / overall_weighted_average) if overall_weighted_average > 0 else 0

        # Step 6: Build response with additional class, subject, assessment type, and teacher details
        response_data = {
            'class_name': class_instance.name,
            'subject_name': subject_instance.name,
            'assessment_type': assessment_type,
            'teacher_name': teacher_instance.username if teacher_instance else 'N/A',
            'performance_data': performance_data_list
        }

        # Return the response with the performance data and additional information
        return Response(response_data, status=status.HTTP_200_OK)

# Class view for fetching normalized performance data of a subject in a Mid-Term or Final Exam assessment type across semesters in a class to compare them on the frontend
class MidTermFinalExamAssessmentComparisonView(APIView):
    permission_classes = [permissions.IsAuthenticated | IsParent | IsTeacher | IsHeadmaster]
    
    def get(self, request, student_id, class_id, subject_id, assessment_type):
        print(assessment_type)

        if not student_id or not subject_id or not assessment_type:
            return Response(
                {"detail": "Missing required parameters: student_id, subject_id, and assessment_type"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch assessments based on provided criteria
        assessments = Assessment.objects.filter(
            student_id=student_id,
            subject=subject_id,
            class_id=class_id,
            assessment_type=assessment_type
        ).order_by('semester', 'date')

        if not assessments.exists():
            return Response(
                {"detail": "No assessments found for the provided criteria."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Fetch class, subject, and teacher details
        class_instance = Class.objects.get(id=class_id)
        subject_instance = Subject.objects.get(id=subject_id)
        teacher_instance = assessments.first().teacher if assessments.exists() else None # Assuming one teacher per class-subject combination

        # Normalize obtained marks across different assessments
        assessment_data = []
        for assessment in assessments:
            if assessment.total_marks and assessment.obtained_marks:
                normalized_score = (assessment.obtained_marks / assessment.total_marks) * 100
                assessment_data.append({
                    "semester": assessment.semester,
                    "date": assessment.date,
                    "total_marks": assessment.total_marks,
                    "obtained_marks": assessment.obtained_marks,
                    "normalized_score": normalized_score,
                })

        # Include class, subject, and teacher information in the response
        response_data = {
            "class_name": class_instance.name,
            "subject_name": subject_instance.name,
            "teacher_name": teacher_instance.username if teacher_instance else "Unknown",
            "assessment_type": assessment_type,
            "assessment_data": assessment_data,
        }

        return Response(response_data, status=status.HTTP_200_OK)

    

# Fetch Overall topic performances in a subject and compare them in the frontend.
class TopicPerformanceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, class_id, subject_id, semester):
        teacher = request.user
        
        # Check if the teacher teaches the specified class and subject
        try:
            teacher_class = TeacherLevelClass.objects.get(teacher=teacher, class_id=class_id)
            if not teacher_class.subjects_taught.filter(id=subject_id).exists():
                return Response({"error": "You are not authorized to view this data."}, status=403)
        except TeacherLevelClass.DoesNotExist:
            return Response({"error": "Class not found."}, status=404)

        # Filter assessments based on class, subject, and semester, and calculate average scores
        assessments = Assessment.objects.filter(
            class_id=class_id,
            subject_id=subject_id,
            semester=semester,
            assessment_type__in=['Exercise', 'Assignment']
        ).values('topic', 'assessment_type').annotate(
            average_score=Avg(
                ExpressionWrapper(
                    F('obtained_marks') * 100.0 / F('total_marks'),
                    output_field=FloatField()
                )
            )
        )
        for item in assessments:
            item['semester'] = semester

        serializer = TopicPerformanceSerializer(assessments, many=True)
        
        return Response(serializer.data)


# Helper function to filter and fetch processed marks
def get_processed_marks_by_academic_year(class_id, academic_year, semester):
    students = ClassEnrollment.objects.filter(
        class_id=class_id, academic_year=academic_year
    ).values_list('student', flat=True)

    return ProcessedMarks.objects.filter(
        student__in=students, class_id=class_id, semester=semester
    )


def consolidate_subject_data(subject_data):
    """Remove duplicate subjects from the subject_data."""
    seen_subjects = set()
    consolidated_data = []

    for subject in subject_data:
        subject_name = subject['subject_name']

        # Check if the subject is already in the consolidated list
        if subject_name not in seen_subjects:
            seen_subjects.add(subject_name)
            consolidated_data.append(subject)

    return consolidated_data


class StudentEndOfSemesterResultView(APIView):
    permission_classes = [permissions.IsAuthenticated]  # Add authentication/permissions if needed
    
    def get(self, request, class_id, student_id, semester):
        try:
            # Retrieve the ProcessedMarks entry for the specified student, class, and semester
            result = ProcessedMarks.objects.get(
                class_id=class_id, 
                student=student_id, 
                semester=semester
            )
            print(result)
            
            # Serialize the result
            serializer = ProcessedMarksSerializer(result)
            
            # Return the serialized data
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except ProcessedMarks.DoesNotExist:
            return Response(
                {"detail": "Result not found for the specified student, class, and semester."},
                status=status.HTTP_404_NOT_FOUND
            )
        
# Fetch Semester Results with class_id, academic year & semester
class SemesterResultsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            # Extract data from the request body
            class_id = request.data.get('class_id')
            academic_year = request.data.get('academic_year')
            semester = request.data.get('semester')

            # Ensure all required parameters are provided
            if not class_id or not academic_year or not semester:
                return Response({'error': 'Missing parameters'}, status=status.HTTP_400_BAD_REQUEST)

            # Fetch results for the current academic year from ClassEnrollment
            processed_marks = get_processed_marks_by_academic_year(class_id, academic_year, semester)
            print(processed_marks)

            # Serialize the results
            serializer = ProcessedMarksSerializer(processed_marks, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsTeacher])
def create_timetable(request):
    class_id = request.data.get('class_id')
    timetable_entries = request.data.get('timetable_entries', [])

    try:
        class_instance = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({"error": "Class not found"}, status=status.HTTP_404_NOT_FOUND)

    # Assign a default class for the 'Break' subject
    break_subject, _ = Subject.objects.get_or_create(
        name='Break',
        defaults={'class_id': class_instance}
    )

    for entry in timetable_entries:
        subject_id = entry.get('subject')
        day = entry.get('day')
        start_time = entry.get('startTime')
        end_time = entry.get('endTime')

        subject_instance = break_subject if not subject_id else Subject.objects.get(id=subject_id)

        # Optional: Retrieve teacher if applicable
        teacher = None
        if subject_id:
            teacher_class = TeacherLevelClass.objects.filter(
                class_id=class_instance,
                subjects_taught=subject_instance
            ).first()
            teacher = teacher_class.teacher if teacher_class else None

        TimeTable.objects.create(
            class_id=class_instance,
            subject=subject_instance,
            teacher=teacher,
            day=day,
            start_time=start_time,
            end_time=end_time,
        )

    return Response({"message": "Timetable entries created successfully"}, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacher | IsHeadmaster | IsParent])
def view_timetable(request, class_id):
    print(class_id)
    timetable = TimeTable.objects.filter(class_id=class_id)
    serializer = TimeTableSerializer(timetable, many=True)
    return Response(serializer.data)

@api_view(['PUT'])
def update_timetable(request, pk):
    """Update a specific timetable entry."""
    try:
        timetable = TimeTable.objects.get(pk=pk)
    except TimeTable.DoesNotExist:
        return Response({"error": "TimeTable entry not found."}, status=status.HTTP_404_NOT_FOUND)

    serializer = TimeTableSerializer(timetable, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE'])
def delete_timetable(request, pk):
    """Delete a specific timetable entry."""
    try:
        timetable = TimeTable.objects.get(pk=pk)
    except TimeTable.DoesNotExist:
        return Response({"error": "TimeTable entry not found."}, status=status.HTTP_404_NOT_FOUND)

    timetable.delete()
    return Response({"message": "TimeTable entry deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class AssessmentNameListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """List all assessment names created by admin (teacher=null)"""
        assessment_names = AssessmentName.objects.filter(teacher__isnull=True)  # Only admin-created
        serializer = AssessmentNameSerializer(assessment_names, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """Create multiple assessment names"""
        data = request.data
        if not isinstance(data, list):  # Handle single object for backward compatibility
            data = [data]

        # Admins create standard names; teachers need class/subject
        is_admin = request.user.roles.filter(name='Admin').exists()  # Adjust role check
        created_assessments = []
        errors = []

        for item in data:
            item_data = item.copy()
            if is_admin:
                item_data['teacher'] = None
                item_data.setdefault('class_id', None)
                item_data.setdefault('subject', None)
            else:
                if 'class_id' not in item_data or 'subject' not in item_data:
                    errors.append({"error": "class_id and subject are required for teachers.", "item": item})
                    continue
                item_data['teacher'] = request.user.id

            serializer = AssessmentNameSerializer(data=item_data)
            if serializer.is_valid():
                serializer.save()
                created_assessments.append(serializer.data)
                logger.info(f"Assessment name '{serializer.data['name']}' created by {request.user.username if not is_admin else 'Admin'}")
            else:
                errors.append(serializer.errors)

        if errors:
            return Response({"created": created_assessments, "errors": errors}, status=status.HTTP_207_MULTI_STATUS)
        return Response(created_assessments, status=status.HTTP_201_CREATED)

class AssessmentNameDetailView(APIView):
    permission_classes = [IsAdminOrAssignedTeacher]  # Admins or assigned teachers can edit/delete

    def get_object(self, pk):
        try:
            return AssessmentName.objects.get(pk=pk)
        except AssessmentName.DoesNotExist:
            return None

    def get(self, request, pk):
        """Retrieve a specific assessment name"""
        assessment_name = self.get_object(pk)
        if not assessment_name:
            return Response({"error": "Assessment name not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = AssessmentNameSerializer(assessment_name)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, pk):
        """Update an assessment name"""
        assessment_name = self.get_object(pk)
        if not assessment_name:
            return Response({"error": "Assessment name not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Ensure the teacher owns this or is Admin
        if not request.user.roles.filter(name='Admin').exists() and assessment_name.teacher != request.user:
            return Response({"error": "You can only edit your own assessment names."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AssessmentNameSerializer(assessment_name, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            logger.info(f"Assessment name '{serializer.data['name']}' updated by {request.user.username}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """Delete an assessment name"""
        assessment_name = self.get_object(pk)
        if not assessment_name:
            return Response({"error": "Assessment name not found."}, status=status.HTTP_404_NOT_FOUND)
        
        # Ensure the teacher owns this or is Admin
        if not request.user.roles.filter(name='Admin').exists() and assessment_name.teacher != request.user:
            return Response({"error": "You can only delete your own assessment names."}, status=status.HTTP_403_FORBIDDEN)

        assessment_name.delete()
        logger.info(f"Assessment name '{assessment_name.name}' deleted by {request.user.username}")
        return Response({"message": "Assessment name deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
    
# View to handle CRUD operations for the Level model
class LevelCRUDView(
    generics.GenericAPIView,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin
):
    """
    CRUD operations for Level model with tenancy restrictions.
    """
    queryset = Level.objects.all()
    serializer_class = LevelSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdminInSchoolOrCampus | IsRegisteredInSchoolOrCampus]  

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:  # Superusers see all
            if user.school:
                queryset = queryset.filter(school=user.school)
            if user.campus:
                queryset = queryset.filter(campus=user.campus)
        return queryset

    def get(self, request, *args, **kwargs):
        if 'pk' in kwargs:
            return self.retrieve(request, *args, **kwargs)
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = request.data
        is_many = isinstance(data, list)
        if not data:
            return Response({"error": "No data provided"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=data, many=is_many)
        serializer.is_valid(raise_exception=True)
        
        self.perform_create(serializer)
        
        if is_many:
            created_names = [item['name'] for item in serializer.data]
            logger.info(f"Levels {created_names} created by {request.user}")
        else:
            logger.info(f"Level '{serializer.data['name']}' created by {request.user}")
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        logger.info(f"Level '{instance.name}' deleted by {request.user}")
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()
        logger.info(f"Level '{serializer.instance.name}' updated by {self.request.user}")


# View to handle CRUD operations for the Terms model
class TermsCRUDView(
    generics.GenericAPIView,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin
):
    """
    CRUD operations for Terms model with tenancy restrictions.
    """
    queryset = Terms.objects.all()
    serializer_class = TermsSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdminInSchoolOrCampus | IsRegisteredInSchoolOrCampus]  
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:  # Superusers see all
            if user.school:
                queryset = queryset.filter(school=user.school)
            if user.campus:
                queryset = queryset.filter(campus=user.campus)
        return queryset

    def get(self, request, *args, **kwargs):
        if 'pk' in kwargs:
            return self.retrieve(request, *args, **kwargs)
        return self.list(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        data = request.data
        is_many = isinstance(data, list)
        if not data:
            return Response({"error": "No data provided"}, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(data=data, many=is_many)
        serializer.is_valid(raise_exception=True)
        
        self.perform_create(serializer)
        
        if is_many:
            created_names = [item['name'] for item in serializer.data]
            logger.info(f"Terms {created_names} created by {request.user}")
        else:
            logger.info(f"Terms '{serializer.data['name']}' created by {request.user}")
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, *args, **kwargs):
        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        return self.partial_update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        instance = self.get_object()
        logger.info(f"Terms '{instance.name}' deleted by {request.user}")
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()
        logger.info(f"Terms '{serializer.instance.name}' updated by {self.request.user}")