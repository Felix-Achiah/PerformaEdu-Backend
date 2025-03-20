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
from user_auth.permissions import IsParent, IsHeadmaster, IsTeacher, IsAdminOrAssignedTeacher, IsAssignedTeacher, IsRegisteredInSchoolOrCampus, IsTeacherOrAdminInSchoolOrCampus, IsHeadmasterInSchoolOrCampus, IsTeacherInSchoolOrCampus, IsParentInSchoolOrCampus
from .models import Class, Subject, TeacherLevelClass, Student, ClassEnrollment, HistoricalClassEnrollment, Assessment, StudentParentRelation, SubjectPerformance, ProcessedMarks, TimeTable, AssessmentName, Level, Terms, ClassSubject
from user_auth.models import User, Role
from user_auth.serializers import UserSerializer
from .serializers import ClassSerializer, SubjectSerializer, TeacherLevelClassSerializer, StudentSerializer, AssessmentSerializer, PromoteStudentsSerializer, ClassEnrollmentSerializer, SubjectPerformanceSerializer, TopicPerformanceSerializer, ProcessedMarksSerializer, StudentParentRelationSerializer, TimeTableSerializer, AssessmentNameSerializer, LevelSerializer, TermsSerializer, ClassSubjectSerializer
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
    """
    Retrieve all classes under a specific level, filtered by the user's school_id.
    Query params:
    - level: The ID of the Level to filter classes by (required)
    """
    if request.method == 'GET':
        user = request.user
        level_id = request.query_params.get('level')  # Expecting level ID, not level_type

        # Check if level_id is provided
        if not level_id:
            return Response({'error': 'Please provide a level parameter with a valid Level ID'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Ensure the level exists
            level = Level.objects.get(id=level_id)
        except Level.DoesNotExist:
            return Response({'error': f'Level with ID {level_id} does not exist'}, status=status.HTTP_404_NOT_FOUND)

        # Base queryset for classes under the specified level
        classes = Class.objects.filter(level=level)

        # Filter by user's school_id from token or user object
        school_id = request.auth.get('school_id') if request.auth else user.school_id
        if school_id:
            classes = classes.filter(school_id=school_id)
        else:
            logger.warning(f"User {user} has no school_id, returning empty class list")
            classes = classes.none()  # Empty queryset if no school

        # Optionally filter by user's campus_id
        campus_id = request.auth.get('campus_id') if request.auth else user.campus_id
        if campus_id:
            classes = classes.filter(campus_id=campus_id)

        # Allow superusers to bypass tenancy filters
        if user.is_superuser:
            classes = Class.objects.filter(level=level)

        if not classes.exists():
            return Response({'message': f'No classes found under Level {level.id} for your school/campus'}, status=status.HTTP_200_OK)

        serializer = ClassSerializer(classes, many=True)
        logger.info(f"User {user} fetched {classes.count()} classes under Level {level.id}")
        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response({'error': 'Method not allowed'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

# Retrieve a specific class endpoint
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacherOrAdminInSchoolOrCampus])
def retrieve_class(request, class_id):
    """
    Retrieve a specific class by ID, ensuring it belongs to the user's school.
    Args:
        class_id: The ID of the class to retrieve.
    """
    try:
        # Fetch the class
        class_obj = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({'error': 'Class not found'}, status=status.HTTP_404_NOT_FOUND)

    # Get user's school_id from token or user object
    user = request.user
    school_id = request.auth.get('school_id') if request.auth else user.school_id

    # Enforce tenancy: Check if the class belongs to the user's school
    if school_id and class_obj.school_id != school_id:
        logger.warning(f"User {user} attempted to access class {class_id} outside their school {school_id}")
        return Response({'error': 'You do not have permission to access this class'}, status=status.HTTP_403_FORBIDDEN)

    # Optionally check campus_id
    campus_id = request.auth.get('campus_id') if request.auth else user.campus_id
    if campus_id and class_obj.campus_id != campus_id:
        logger.warning(f"User {user} attempted to access class {class_id} outside their campus {campus_id}")
        return Response({'error': 'You do not have permission to access this class'}, status=status.HTTP_403_FORBIDDEN)

    # Serialize and return the class
    serializer = ClassSerializer(class_obj)
    logger.info(f"User {user} retrieved class {class_obj.id}")
    return Response(serializer.data, status=status.HTTP_200_OK)

# Update endpoint
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated, IsTeacherOrAdminInSchoolOrCampus])
def update_class(request, class_id):
    """
    Update a class, ensuring it belongs to the user's school.
    Args:
        class_id: The ID of the class to update.
    """
    try:
        class_obj = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({'error': 'Class not found'}, status=status.HTTP_404_NOT_FOUND)

    # Get user's school_id and campus_id from token or user object
    user = request.user
    school_id = request.auth.get('school_id') if request.auth else user.school_id
    campus_id = request.auth.get('campus_id') if request.auth else user.campus_id

    # Enforce tenancy: Check if the class belongs to the user's school
    if school_id and class_obj.school_id != school_id:
        logger.warning(f"User {user} attempted to update class {class_id} outside their school {school_id}")
        return Response({'error': 'You do not have permission to update this class'}, status=status.HTTP_403_FORBIDDEN)

    # Optionally check campus_id
    if campus_id and class_obj.campus_id != campus_id:
        logger.warning(f"User {user} attempted to update class {class_id} outside their campus {campus_id}")
        return Response({'error': 'You do not have permission to update this class'}, status=status.HTTP_403_FORBIDDEN)

    # Allow superusers to bypass tenancy restrictions
    if user.is_superuser:
        pass  # No additional filtering needed

    # Update the class
    serializer = ClassSerializer(class_obj, data=request.data, partial=True)  # Use PUT (full update)
    if serializer.is_valid():
        serializer.save()
        logger.info(f"User {user} updated class {class_id}")
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# Delete endpoint
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated, IsTeacherOrAdminInSchoolOrCampus])
def delete_class(request, class_id):
    """
    Delete a class, ensuring it belongs to the user's school.
    Args:
        class_id: The ID of the class to delete.
    """
    try:
        class_obj = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({'error': 'Class not found'}, status=status.HTTP_404_NOT_FOUND)

    # Get user's school_id and campus_id from token or user object
    user = request.user
    school_id = request.auth.get('school_id') if request.auth else user.school_id
    campus_id = request.auth.get('campus_id') if request.auth else user.campus_id

    # Enforce tenancy: Check if the class belongs to the user's school
    if school_id and class_obj.school_id != school_id:
        logger.warning(f"User {user} attempted to delete class {class_id} outside their school {school_id}")
        return Response({'error': 'You do not have permission to delete this class'}, status=status.HTTP_403_FORBIDDEN)

    # Optionally check campus_id
    if campus_id and class_obj.campus_id != campus_id:
        logger.warning(f"User {user} attempted to delete class {class_id} outside their campus {campus_id}")
        return Response({'error': 'You do not have permission to delete this class'}, status=status.HTTP_403_FORBIDDEN)

    # Allow superusers to bypass tenancy restrictions
    if user.is_superuser:
        pass  # No additional filtering needed

    # Delete the class
    class_obj.delete()
    logger.info(f"User {user} deleted class {class_id}")
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

# View to handle CRUD operations for the Subject model
class SubjectCRUDView(
    generics.GenericAPIView,
    ListModelMixin,
    CreateModelMixin,
    RetrieveModelMixin,
    UpdateModelMixin,
    DestroyModelMixin
):
    """
    CRUD operations for Subject model with tenancy restrictions.
    """
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer

    # Default permissions
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        """
        Assign different permissions based on the request method.
        """
        if self.request.method in ["GET"]:  # List and Retrieve
            return [permissions.IsAuthenticated(), IsRegisteredInSchoolOrCampus()]
        
        elif self.request.method in ["POST", "PUT", "PATCH"]:  # Create and Update
            return [permissions.IsAuthenticated(), IsTeacherOrAdminInSchoolOrCampus()]
        
        elif self.request.method == "DELETE":  # Delete
            return [permissions.IsAuthenticated(), IsTeacherOrAdminInSchoolOrCampus(), permissions.IsAdminUser()]
        
        return super().get_permissions()

    def get_queryset(self):
        """
        Filter subjects to only those in the user's school/campus.
        """
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:  # Superusers see all
            if user.school:
                queryset = queryset.filter(school=user.school)
            if user.campus:
                queryset = queryset.filter(campus=user.campus)
        return queryset

    def get_object(self):
        """
        Optimize retrieval with select_related for school and campus.
        """
        queryset = self.get_queryset().select_related('school', 'campus')
        obj = generics.get_object_or_404(queryset, pk=self.kwargs['pk'])
        return obj

    def check_tenancy(self, instance):
        """
        Helper method to check if the instance belongs to the user's school/campus.
        Allows actions within the same school even if campus differs.
        """
        user = self.request.user
        school_id = self.request.auth.get('school_id') if self.request.auth else user.school_id
        campus_id = self.request.auth.get('campus_id') if self.request.auth else user.campus_id

        if school_id and instance.school_id != school_id:
            logger.warning(f"User {user} denied access to subject {instance.id} (school mismatch: {school_id} vs {instance.school_id})")
            return False
        
        # Granular campus check: Allow if school matches, even if campus differs
        if campus_id and instance.campus_id != campus_id:
            if instance.school_id != school_id:
                logger.warning(f"User {user} denied access to subject {instance.id} (campus mismatch: {campus_id} vs {instance.campus_id}, school mismatch)")
                return False
        
        return True

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
            logger.info(f"Subjects {created_names} created by {request.user}")
        else:
            logger.info(f"Subject '{serializer.data['name']}' created by {request.user}")
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, *args, **kwargs):
        """
        Update a subject (full update) with tenancy enforcement.
        """
        instance = self.get_object()
        
        if not self.check_tenancy(instance) and not request.user.is_superuser:
            return Response({'error': 'You do not have permission to update this subject'}, status=status.HTTP_403_FORBIDDEN)

        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        """
        Update a subject (partial update) with tenancy enforcement.
        """
        instance = self.get_object()
        
        if not self.check_tenancy(instance) and not request.user.is_superuser:
            return Response({'error': 'You do not have permission to update this subject'}, status=status.HTTP_403_FORBIDDEN)

        return self.partial_update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """
        Delete a subject with tenancy enforcement.
        """
        instance = self.get_object()
        
        if not self.check_tenancy(instance) and not request.user.is_superuser:
            return Response({'error': 'You do not have permission to delete this subject'}, status=status.HTTP_403_FORBIDDEN)

        logger.info(f"Subject '{instance.name}' deleted by {request.user}")
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()
        logger.info(f"Subject '{serializer.instance.name}' updated by {self.request.user}")


class ManageClassSubjectsView(generics.GenericAPIView):
    """
    API View to assign, update, delete, and list subjects assigned to a class.
    """
    permission_classes = [permissions.IsAuthenticated, IsTeacherInSchoolOrCampus]  
    serializer_class = ClassSubjectSerializer

    def get_queryset(self):
        """Filter subjects based on the class ID and user's school/campus."""
        user = self.request.user
        queryset = ClassSubject.objects.all()
        
        if not user.is_superuser:
            if user.school:
                queryset = queryset.filter(school=user.school)
            if user.campus:
                queryset = queryset.filter(campus=user.campus)
        
        return queryset

    def get(self, request, class_id):
        """
        List all subjects assigned to a specific class.
        """
        subjects = self.get_queryset().filter(class_id=class_id)
        serializer = self.get_serializer(subjects, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Assign one or multiple subjects to a class.
        """
        class_id = request.data.get("class_id")
        subject_ids = request.data.get("subject_ids", [])  # List of subjects
        
        if not class_id or not subject_ids:
            return Response({"error": "class_id and subject_ids are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            class_instance = Class.objects.get(id=class_id)
        except Class.DoesNotExist:
            return Response({"error": "Class not found"}, status=status.HTTP_404_NOT_FOUND)

        assigned_subjects = []
        for subject_id in subject_ids:
            try:
                subject_instance = Subject.objects.get(id=subject_id)
                class_subject, created = ClassSubject.objects.get_or_create(
                    class_id=class_instance,
                    subject=subject_instance,
                    school=class_instance.school,
                    campus=class_instance.campus,
                    assigned_by=request.user
                )
                assigned_subjects.append(class_subject)
            except Subject.DoesNotExist:
                return Response({"error": f"Subject with ID {subject_id} not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(assigned_subjects, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def put(self, request, pk):
        """
        Update a specific class-subject assignment.
        """
        try:
            class_subject = ClassSubject.objects.get(id=pk)
        except ClassSubject.DoesNotExist:
            return Response({"error": "Assignment not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(class_subject, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(assigned_by=request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        """
        Delete an assigned subject from a class.
        """
        try:
            class_subject = ClassSubject.objects.get(id=pk)
        except ClassSubject.DoesNotExist:
            return Response({"error": "Assignment not found"}, status=status.HTTP_404_NOT_FOUND)

        class_subject.delete()
        return Response({"message": "Subject removed from class"}, status=status.HTTP_204_NO_CONTENT)
    
        
# Update Subjects registered to a Teacher
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated, IsTeacherOrAdminInSchoolOrCampus])
def update_teacher_subjects(request, class_id):
    """
    Update a TeacherLevelClass instance, ensuring it belongs to the user's school/campus.
    Args:
        class_id: The ID of the class tied to the TeacherLevelClass.
    """
    try:
        # Optimize with select_related for class, school, and campus
        teacher_level_class = TeacherLevelClass.objects.select_related(
            'class__school', 'class__campus'
        ).get(teacher=request.user, class_id=class_id)
    except TeacherLevelClass.DoesNotExist:
        return Response({'error': 'TeacherLevelClass not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Extract the class object for tenancy check
    class_obj = teacher_level_class.class_obj  # Assuming 'class_obj' is the ForeignKey field name

    # Tenancy check
    user = request.user
    school_id = request.auth.get('school_id') if request.auth else user.school_id
    campus_id = request.auth.get('campus_id') if request.auth else user.campus_id

    # Reusable tenancy logic
    if school_id and class_obj.school_id != school_id:
        logger.warning(f"User {user} attempted to update TeacherLevelClass for class {class_id} outside their school {school_id}")
        return Response({'error': 'You do not have permission to update this teacher-class assignment'}, status=status.HTTP_403_FORBIDDEN)

    # Granular campus check: Allow if school matches, even if campus differs
    if campus_id and class_obj.campus_id != campus_id:
        if class_obj.school_id != school_id:
            logger.warning(f"User {user} attempted to update TeacherLevelClass for class {class_id} outside their campus {campus_id} and school {school_id}")
            return Response({'error': 'You do not have permission to update this teacher-class assignment'}, status=status.HTTP_403_FORBIDDEN)

    # Allow superusers to bypass tenancy restrictions
    if user.is_superuser:
        pass

    # Update the TeacherLevelClass
    serializer = TeacherLevelClassSerializer(
        teacher_level_class, data=request.data, partial=True, context={'request': request}
    )
    if serializer.is_valid():
        serializer.save()
        logger.info(f"User {user} updated TeacherLevelClass for class {class_id}")
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_teacher_registered_subjects(request, class_id):
    """
    Retrieve subjects registered to a teacher for a specific class, ensuring tenancy.
    Args:
        class_id: The ID of the class to retrieve subjects for.
    """
    try:
        teacher_id = int(request.user.id)
        # Optimize with select_related for class, school, and campus
        teacher_level_class = TeacherLevelClass.objects.select_related(
            'class_obj__school', 'class_obj__campus'
        ).get(teacher_id=teacher_id, class_id=class_id)
    except TeacherLevelClass.DoesNotExist:
        return Response({'subjects_taught_details': []}, status=status.HTTP_200_OK)

    # Extract the class object for tenancy check
    class_obj = teacher_level_class.class_obj  # Assuming 'class_obj' is the ForeignKey field name

    # Tenancy check
    user = request.user
    school_id = request.auth.get('school_id') if request.auth else user.school_id
    campus_id = request.auth.get('campus_id') if request.auth else user.campus_id

    # Enforce tenancy: Check if the class belongs to the user's school
    if school_id and class_obj.school_id != school_id:
        logger.warning(f"User {user} attempted to access subjects for class {class_id} outside their school {school_id}")
        return Response({'subjects_taught_details': [], 'error': 'Class not in your school'}, status=status.HTTP_200_OK)

    # Granular campus check: Allow if school matches, even if campus differs
    if campus_id and class_obj.campus_id != campus_id:
        if class_obj.school_id != school_id:
            logger.warning(f"User {user} attempted to access subjects for class {class_id} outside their campus {campus_id} and school {school_id}")
            return Response({'subjects_taught_details': [], 'error': 'Class not in your campus or school'}, status=status.HTTP_200_OK)

    # Allow superusers to bypass tenancy restrictions
    if user.is_superuser:
        pass  # No filtering needed

    # Serialize and return the data
    serializer = TeacherLevelClassSerializer(teacher_level_class)
    logger.info(f"User {user} retrieved subjects for class {class_id}")
    return Response([serializer.data], status=status.HTTP_200_OK)


''' PROMOTE STUDENTS OR A STUDENT TO A DIFFERENT CLASS'''

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus, IsAssignedTeacher])
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
            student = get_object_or_404(User, id=student_id)

            # Ensure the user has a "Student" role
            if not student.has_role('Student'):
                logger.warning(f"User {student.id} is not a student, skipping promotion")
                continue

            # Ensure the student belongs to the same school/campus
            if student.school_id != request.user.school_id:
                logger.warning(f"Student {student.id} does not belong to the same school, skipping")
                continue

            # Check existing enrollment
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
                'student_name': student.username or student.email,
                'new_class_id': new_class.id,
                'new_class_name': new_class.name,
                'enrollment_date': new_enrollment.academic_year
            })

        return Response({
            'message': 'Students promoted successfully',
            'promoted_students': promoted_students
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error promoting students: {str(e)}")
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
@permission_classes([permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus])
def get_promoted_existing_repeated_students(request, class_id):
    try:
        new_class = get_object_or_404(Class, id=class_id)

        # Fetch school and campus of the authenticated user
        user = request.user
        user_school_id = user.school_id
        user_campus_id = user.campus_id

        # Ensure the class enrollment belongs to the same school/campus as the user
        promoted_enrollments = ClassEnrollment.objects.filter(
            class_id=new_class, status='promoted',
            school_id=user_school_id, campus_id=user_campus_id
        ).select_related('student')

        existing_enrollments = ClassEnrollment.objects.filter(
            class_id=new_class, status='existing',
            school_id=user_school_id, campus_id=user_campus_id
        ).select_related('student')

        repeated_enrollments = ClassEnrollment.objects.filter(
            class_id=new_class, status='repeated',
            school_id=user_school_id, campus_id=user_campus_id
        ).select_related('student')

        promoted_students_data = []
        for enrollment in promoted_enrollments:
            historical_enrollment = HistoricalClassEnrollment.objects.filter(student=enrollment.student).order_by('-id').first()
            previous_class_name = historical_enrollment.class_enrolled.name if historical_enrollment else None
            student_data = StudentSerializer(enrollment.student).data
            student_data['previous_class_name'] = previous_class_name
            promoted_students_data.append(student_data)

        existing_students_data = StudentSerializer(
            [enrollment.student for enrollment in existing_enrollments], many=True
        ).data

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
@permission_classes([permissions.IsAuthenticated, IsTeacher, IsAssignedTeacher])
def merge_promoted_repeated_students(request):
    student_ids = request.data.get('student_ids', [])
    class_id = request.data.get('class_id')  # Ensure class_id is included in the request

    if not student_ids or not class_id:
        return Response({"error": "Missing required parameters."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Verify that the class exists
        target_class = get_object_or_404(Class, id=class_id)

        # Get user school and campus
        user = request.user
        user_school_id = user.school_id
        user_campus_id = user.campus_id

        # Check tenancy: Ensure the class belongs to the same school/campus
        if target_class.school_id != user_school_id or target_class.campus_id != user_campus_id:
            return Response({"error": "Permission denied. You are not assigned to this class."}, status=status.HTTP_403_FORBIDDEN)

        for student_id in student_ids:
            student = get_object_or_404(User, id=student_id, roles__name="Student")

            # Find enrollments where the student is promoted or repeated in the given class
            class_enrollments = ClassEnrollment.objects.filter(
                student=student,
                class_id=target_class,
                status__in=['promoted', 'repeated'],
                school_id=user_school_id,
                campus_id=user_campus_id
            )

            if not class_enrollments.exists():
                return Response({"error": f"Student {student_id} is not enrolled as 'promoted' or 'repeated' in this class."},
                                status=status.HTTP_400_BAD_REQUEST)

            # Update status to 'existing'
            class_enrollments.update(status='existing')

        return Response({"message": "Students merged successfully."}, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus])
def get_students_by_class_id(request):
    class_id = request.query_params.get('class_id')
    if not class_id:
        return Response({'error': 'Class ID parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        # Get the authenticated user's school and campus
        user = request.user
        user_school_id = user.school_id
        user_campus_id = user.campus_id

        # Ensure that the class exists and belongs to the same school and campus
        target_class = get_object_or_404(Class, id=class_id, school_id=user_school_id, campus_id=user_campus_id)

        # Get 'Student' role
        student_role = Role.objects.get(name='Student')

        # Fetch enrollments by class, status, and tenancy
        enrollments = ClassEnrollment.objects.filter(
            class_id=target_class,
            status='existing',
            student__roles=student_role,
            school_id=user_school_id,
            campus_id=user_campus_id
        ).select_related('student', 'class_id', 'academic_year')

        if not enrollments.exists():
            return Response({'error': f"No students found for class {target_class.name} with status 'existing'"},
                            status=status.HTTP_404_NOT_FOUND)

        logger.info(f"Enrollments found: {enrollments.count()}")
        serializer = ClassEnrollmentSerializer(enrollments, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Role.DoesNotExist:
        return Response({'error': "Role 'Student' does not exist"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Update a specific student
@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated, IsTeacherOrAdminInSchoolOrCampus])
def update_student(request, student_id):
    try:
        student = User.objects.get(id=student_id)
    except User.DoesNotExist:
        return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Get the authenticated user's school and campus
    user = request.user
    user_school_id = user.school_id
    user_campus_id = user.campus_id

    # Ensure the student belongs to the same school and campus
    if student.school_id != user_school_id or student.campus_id != user_campus_id:
        return Response(
            {'error': 'You are not authorized to update this student.'},
            status=status.HTTP_403_FORBIDDEN
        )

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
@permission_classes([permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus])
def get_student(request, student_id):
    try:
        # Ensure the student exists and has the 'Student' role
        student = User.objects.filter(
            id=student_id,
            roles__name='Student'
        ).select_related('school', 'campus').first()

        if not student:
            return Response({'error': 'Student not found or does not have the Student role.'}, status=status.HTTP_404_NOT_FOUND)

        # Check tenancy: Ensure the requester belongs to the same school and campus as the student
        if request.user.school_id != student.school_id or request.user.campus_id != student.campus_id:
            return Response({'error': 'You are not authorized to access this student.'}, status=status.HTTP_403_FORBIDDEN)

        # Serialize and return student data
        serializer = StudentSerializer(student)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


'''STUDENT ASSESSTMENT ENDPOINTS'''

# Create student assesstment 
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsTeacherInSchoolOrCampus])
def create_assessments(request):
    if request.method == 'POST':
        teacher = request.user  # Get the authenticated teacher

        # Ensure teacher is registered to a school and campus
        if not teacher.school or not teacher.campus:
            return Response({'error': 'Teacher must be registered to a school and campus.'}, status=status.HTTP_403_FORBIDDEN)

        assessments_data = request.data.get('assessments', [])  # Get the list of assessment data from the request
        created_assessments = []
        errors = []

        for data in assessments_data:
            # Extract class, subject, and student marks data
            class_id = data.pop('class_id')
            subject_id = data.pop('subject')
            students_data = data.pop('student_marks', [])

            try:
                # Fetch class and subject with tenancy check
                class_obj = Class.objects.get(id=class_id, school=teacher.school, campus=teacher.campus)
                subject = Subject.objects.get(id=subject_id, school=teacher.school, campus=teacher.campus)

                # Check if the teacher is assigned to teach the subject in the specified class
                teacher_level_class = TeacherLevelClass.objects.filter(
                    teacher=teacher, class_id=class_obj, subjects_taught=subject
                ).first()
                if not teacher_level_class:
                    errors.append({'error': f'Teacher is not assigned to teach subject ID {subject_id} in class ID {class_id} at this school/campus.'})
                    continue

                for student_data in students_data:
                    student_id = student_data.get('id')
                    obtained_marks = student_data.get('obtained_marks')

                    try:
                        # Fetch student with tenancy check
                        student = User.objects.get(id=student_id, roles__name='Student', school=teacher.school, campus=teacher.campus)

                        # Validate and convert total_marks and obtained_marks to Decimal
                        total_marks = data.get('total_marks', '0.00')
                        obtained_marks = obtained_marks if obtained_marks not in [None, ""] else "0.00"

                        try:
                            total_marks = Decimal(total_marks)
                            obtained_marks = Decimal(obtained_marks)
                        except InvalidOperation:
                            errors.append({'error': f"Invalid marks format for student ID {student_id}."})
                            continue

                        # Create the assessment entry
                        assessment_instance = Assessment.objects.create(
                            student=student,
                            class_id=class_obj,
                            teacher=teacher,
                            subject=subject,
                            school=teacher.school,
                            campus=teacher.campus,
                            total_marks=total_marks,
                            topic=data.get('topic'),
                            assessment_name=data.get('assessment_type'),
                            term=data.get('term'),
                            date=data.get('date'),
                            obtained_marks=obtained_marks
                        )
                        created_assessments.append(assessment_instance)
                    except User.DoesNotExist:
                        errors.append({'error': f"Student ID {student_id} does not exist in this school and campus."})

            except Class.DoesNotExist:
                errors.append({'error': f"Class ID {class_id} does not exist in this school and campus."})
            except Subject.DoesNotExist:
                errors.append({'error': f"Subject ID {subject_id} does not exist in this school and campus."})

        if errors:
            return Response(errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            # Serialize the created assessment instances
            serializer = AssessmentSerializer(created_assessments, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response({'error': 'Invalid request method.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus])
def fetch_historical_assessment_data(request):
    try:
        # Extract parameters from request data
        student_id = request.data.get('student_id')
        class_id = request.data.get('class_id')
        academic_year = request.data.get('academic_year')
        assessment_name = request.data.get('assessment_name')  # Updated field
        subject_id = request.data.get('subject_id')
        semester = request.data.get('semester')
        school_id = request.data.get('school_id')
        campus_id = request.data.get('campus_id')

        # Ensure required fields are provided
        if not all([student_id, class_id, academic_year, school_id, campus_id]):
            return Response({'error': 'Missing required fields'}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch student (user with role 'Student') and class instance
        student = User.objects.get(id=student_id, roles__name="Student")
        class_instance = Class.objects.get(id=class_id)

        # Verify student enrollment in school and campus
        current_enrollment = ClassEnrollment.objects.filter(
            student=student,
            class_id=class_instance,
            academic_year=academic_year,
            school_id=school_id,
            campus_id=campus_id,
        ).exists()

        historical_enrollment = HistoricalClassEnrollment.objects.filter(
            student=student,
            class_enrolled=class_instance,
            academic_year=academic_year,
            school_id=school_id,
            campus_id=campus_id,
        ).exists()

        if not current_enrollment and not historical_enrollment:
            message = f"Sorry, {student.username} wasn't enrolled in {class_instance.name} at school {school_id} (campus {campus_id}) in {academic_year}."
            return Response({'error': message}, status=status.HTTP_400_BAD_REQUEST)

        # Filter assessments by school, campus, and assessment_name
        assessments = Assessment.objects.filter(
            student=student,
            class_id=class_instance,
            subject_id=subject_id,
            assessment_name=assessment_name,  # Updated filtering
            school_id=school_id,
            campus_id=campus_id,
        )

        # Apply semester filtering if applicable
        if assessment_name in ['Exercise', 'Assignment'] and semester:
            assessments = assessments.filter(semester=semester)
        elif assessment_name not in ['Exercise', 'Assignment', 'Final Exams', 'Mid Term Exams']:
            assessments = assessments.exclude(semester__in=['1st Semester', '2nd Semester'])

        # Serialize and return the assessments
        serializer = AssessmentSerializer(assessments, many=True)
        return Response({'assessments': serializer.data}, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response({'error': 'Student not found or does not have the Student role.'}, status=status.HTTP_404_NOT_FOUND)
    except Class.DoesNotExist:
        return Response({'error': 'Class not found.'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus])
def get_student_assessments(request, student_id, term, subject_id, assessment_name, school_id, campus_id):
    try:
        # Retrieve assessments based on provided filters
        assessments = Assessment.objects.filter(
            school=school_id,
            campus=campus_id,
            student=student_id,
            term=term,
            subject=subject_id,
            assessment_name=assessment_name
        )
        
        # Serialize the assessments
        serializer = AssessmentSerializer(assessments, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    

# Get Student Mid Term or Final Exam assessment
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus])
def get_student_exams_assessments(request, student_id, subject_id, assessment_name, school_id, campus_id):
    try:
        # Retrieve assessments based on provided filters
        assessments = Assessment.objects.filter(
            school=school_id,
            campus=campus_id,
            student=student_id,
            subject=subject_id,
            assessment_name=assessment_name
        )
        
        # Serialize the assessments
        serializer = AssessmentSerializer(assessments, many=True)
        return Response(serializer.data)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus])
def get_student_assessment(request, student_id, assessment_id, school_id, campus_id):
    try:
        # Retrieve the specific assessment based on student_id and assessment_id
        assessment = Assessment.objects.get(
            school=school_id,
            campus=campus_id,
            student=student_id,
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
@permission_classes([permissions.IsAuthenticated, IsTeacherInSchoolOrCampus])
def update_assessments(request):
    if request.method == 'PUT':
        teacher = request.user  # Get the authenticated user (teacher)

        assessments_data = request.data.get('assessments', [])  # List of assessments to update
        
        updated_assessments = []
        errors = []
        
        for data in assessments_data:
            assessment_id = data.pop('assessment_id', None)
            class_id = data.pop('class_id', None)
            subject_id = data.pop('subject', None)
            student_id = data.pop('student', None)
            school_id = data.pop('school', None)
            campus_id = data.pop('campus', None)
            obtained_marks = data.pop('obtained_marks', None)

            # Validate required fields
            if not all([assessment_id, class_id, subject_id, student_id, school_id, campus_id]):
                errors.append({'detail': 'Missing required fields in request data.', 'assessment_id': assessment_id})
                continue

            # Fetch related models
            try:
                class_instance = Class.objects.get(pk=class_id)
                student_instance = User.objects.get(pk=student_id, roles__name='Student')
                subject_instance = Subject.objects.get(pk=subject_id)

                # Fetch assessment and ensure it matches school & campus
                assessment_instance = Assessment.objects.get(
                    pk=assessment_id, school_id=school_id, campus_id=campus_id
                )
            except Class.DoesNotExist:
                errors.append({'detail': f'Class with ID {class_id} not found.', 'assessment_id': assessment_id})
                continue
            except User.DoesNotExist:
                errors.append({'detail': f'Student with ID {student_id} not found.', 'assessment_id': assessment_id})
                continue
            except Subject.DoesNotExist:
                errors.append({'detail': f'Subject with ID {subject_id} not found.', 'assessment_id': assessment_id})
                continue
            except Assessment.DoesNotExist:
                errors.append({'detail': f'Assessment with ID {assessment_id} does not exist in the specified school and campus.', 'assessment_id': assessment_id})
                continue

            # Ensure the teacher is assigned to teach this subject in the class
            teacher_level_class = TeacherLevelClass.objects.filter(
                teacher=teacher, class_id=class_instance, subjects_taught=subject_instance
            ).exists()

            if not teacher_level_class:
                errors.append({'detail': f'Teacher is not assigned to teach subject {subject_id} in class {class_id}.', 'assessment_id': assessment_id})
                continue

            # Update the assessment instance
            update_data = {
                'obtained_marks': obtained_marks,
                'student': student_instance.pk,
                'teacher': teacher.pk,
                'subject': subject_instance.pk,
                'class_id': class_instance.pk,
            }

            serializer = AssessmentSerializer(assessment_instance, data=update_data, partial=True)
            if serializer.is_valid():
                updated_instance = serializer.save()
                updated_assessments.append(updated_instance)
            else:
                errors.append({'assessment_id': assessment_id, 'errors': serializer.errors})

        if errors:
            return Response({'errors': errors}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response(AssessmentSerializer(updated_assessments, many=True).data, status=status.HTTP_200_OK)

    

# Delete a student's assessment
@api_view(['DELETE'])
@permission_classes([permissions.IsAuthenticated, IsTeacherInSchoolOrCampus])
def delete_assessment(request, student_id, assessment_id, school_id, campus_id):
    teacher = request.user  # Get the authenticated teacher

    # Step 1: Check if the student exists
    try:
        student = User.objects.get(pk=student_id, roles__name='Student')
    except User.DoesNotExist:
        return Response({'detail': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Step 2: Check if the assessment exists and belongs to the school/campus
    try:
        assessment = Assessment.objects.get(
            pk=assessment_id, student=student, school_id=school_id, campus_id=campus_id
        )
    except Assessment.DoesNotExist:
        return Response({'detail': 'Assessment not found for the student in this school and campus.'}, status=status.HTTP_404_NOT_FOUND)

    # Step 3: Check if the teacher is assigned to teach the subject in this class
    is_teacher_assigned = TeacherLevelClass.objects.filter(
        teacher=teacher,
        class_id=assessment.class_id,
        subjects_taught=assessment.subject
    ).exists()

    if not is_teacher_assigned:
        return Response(
            {'detail': 'You are not assigned to teach this subject in this class. You cannot delete this assessment.'},
            status=status.HTTP_403_FORBIDDEN
        )

    # Step 4: Delete the assessment
    assessment.delete()

    return Response({'detail': 'Assessment deleted successfully.'}, status=status.HTTP_204_NO_CONTENT)



# Fetch Classes a Teacher teaches subject(s) in
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacherInSchoolOrCampus])
def get_teacher_classes(request):
    teacher_id = request.user.id
    school_id = request.query_params.get('school_id')
    campus_id = request.query_params.get('campus_id')

    # Filter classes by teacher, school, and campus
    teacher_classes = TeacherLevelClass.objects.filter(teacher_id=teacher_id)

    if school_id:
        teacher_classes = teacher_classes.filter(school_id=school_id)

    if campus_id:
        teacher_classes = teacher_classes.filter(campus_id=campus_id)

    # Serialize the filtered data
    serializer = TeacherLevelClassSerializer(teacher_classes, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)



@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacherInSchoolOrCampus])
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
@permission_classes([permissions.IsAuthenticated, IsParentInSchoolOrCampus])
def assign_students_to_parents(request):
    user = request.user

    # Ensure only parents can assign students
    if not user.has_role('Parent'):
        return Response({'error': 'Only parents can assign students'}, status=status.HTTP_403_FORBIDDEN)

    student_ids = request.data.get('student_ids')
    if not student_ids:
        return Response({'error': 'No students selected'}, status=status.HTTP_400_BAD_REQUEST)

    school_id = user.school_id
    campus_id = user.campus_id

    assigned_students = []
    errors = []

    for student_id in student_ids:
        try:
            # Filter students by school, campus, and role (Student)
            student = User.objects.get(id=student_id, roles__name='Student', school_id=school_id, campus_id=campus_id)
            
            # Ensure the student is not already assigned to two parents
            if StudentParentRelation.objects.filter(student=student).count() >= 2:
                errors.append({'error': f'Student {student.username} is already assigned to two parents'})
                continue

            # Ensure the student is not already assigned to this parent
            if StudentParentRelation.objects.filter(student=student, parent=user).exists():
                errors.append({'error': f'Student {student.username} is already assigned to you'})
                continue

            # Assign the student to the parent
            StudentParentRelation.objects.get_or_create(student=student, parent=user)
            assigned_students.append(student.username)

        except User.DoesNotExist:
            errors.append({'error': f'Student with ID {student_id} not found in your school or campus'})

    # Construct the response
    if errors:
        return Response({'assigned_students': assigned_students, 'errors': errors}, status=status.HTTP_400_BAD_REQUEST)

    return Response({'message': 'Students assigned successfully', 'assigned_students': assigned_students}, status=status.HTTP_200_OK)


# Fetch students assigned to a Parent as children
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsParentInSchoolOrCampus])
def get_students_assigned_to_parent(request):
    user = request.user

    if user.has_role('Parent'):
        return Response({'error': 'Only parents can retrieve assigned students'}, status=status.HTTP_403_FORBIDDEN)

    assigned_students = StudentParentRelation.objects.filter(parent=user).select_related('student')

    students = [relation.student for relation in assigned_students]

    serializer = UserSerializer(students, many=True)

    return Response(serializer.data, status=status.HTTP_200_OK)

# Get Student and Parent info
class StudentParentRelationView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus]

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
@permission_classes([permissions.IsAuthenticated, IsParentInSchoolOrCampus])
def delete_child(request, student_id):
    # Ensure the user is a parent
    if not request.user.has_role('Parent'):
        return Response({'error': 'You do not have permission to perform this action.'}, status=status.HTTP_403_FORBIDDEN)

    # Try to get the StudentParentRelation object (get_object_or_404 will raise 404 if not found)
    relation = get_object_or_404(StudentParentRelation, student__id=student_id, parent=request.user)

    # Delete the relationship
    relation.delete()

    return Response({'message': 'Student successfully removed from your children list.'}, status=status.HTTP_204_NO_CONTENT)


class ChildrenPerformanceView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsParentInSchoolOrCampus]

    def get(self, request, class_id, student_id, term, assessment_name, subject_id):
        try:
            student = User.objects.get(id=student_id)
            class_instance = Class.objects.get(id=class_id)

            assessments = Assessment.objects.filter(
                student_id=student_id,
                class_id=class_id,
                subject=subject_id,
                assessment_name=assessment_name,
            )


            serializer = AssessmentSerializer(assessments, many=True)
            return Response({'assessments': serializer.data}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
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
            assessment_name = request.data.get('assessment_name')
            subject_id = request.data.get('subject_id')
            term = request.data.get('term')

            # Perform the semester and assessment type check to filter data
            if assessment_name in ['Exercise', 'Assignment'] and term:
                assessments = Assessment.objects.filter(
                    student_id=student_id,
                    class_id=class_id,
                    subject=subject_id,
                    assessment_name=assessment_name,
                    term=term
                )
            elif assessment_name not in ['Exercise', 'Assignment', 'Final Exams', 'Mid Term Exams']:
                assessments = Assessment.objects.filter(
                    student_id=student_id,
                    class_id=class_id,
                    subject=subject_id,
                    assessment_name=assessment_name
                ).exclude(
                    semester__in=['1st Semester', '2nd Semester']
                )
            else:
                assessments = Assessment.objects.filter(
                    student_id=student_id,
                    class_id=class_id,
                    subject=subject_id,
                    assessment_type=assessment_name
                )

            # Serialize the filtered queryset into JSON
            serializer = AssessmentSerializer(assessments, many=True)
            return Response({'assessments': serializer.data}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            return Response({'error': 'Student not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Class.DoesNotExist:
            return Response({'error': 'Class not found.'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        

class HistoricalSubjectPerformanceView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus]

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
    permission_classes = [permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus]

    def get(self, request, student_id):
        # Get the requesting user's school and campus
        user = request.user
        school_id = user.school_id
        campus_id = user.campus_id

        if not school_id or not campus_id:
            return Response(
                {"detail": "User is not associated with a school or campus."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Ensure the student belongs to the same school and campus as the requesting user
        student = get_object_or_404(
            User,
            id=student_id,
            roles__name='Student',
            school_id=school_id,
            campus_id=campus_id
        )

        # Filter assessments by student, school, and campus
        assessments = Assessment.objects.filter(
            student=student,
            school_id=school_id,
            campus_id=campus_id
        )

        if not assessments.exists():
            return Response(
                {"detail": "No assessments found for this student in your school and campus."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Calculate average score for each subject per academic year and class
        performances = assessments.values(
            'subject', 'class_id', 'class_id__academic_year'
        ).annotate(
            term_score=Avg('obtained_marks')
        ).values(
            'subject', 'class_id', 'class_id__academic_year'
        ).annotate(
            academic_year_average=Avg('term_score')
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
    permission_classes = [permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus]

    def get(self, request, student_id, class_id, subject_id, term):
        # Calculate counts and average marks for both exercises and assignments
        topic_performance = Assessment.objects.filter(
            student_id=student_id,
            class_id=class_id,
            subject_id=subject_id,
            term=term,
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
    permission_classes = [permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus]

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
@permission_classes([permissions.IsAuthenticated, IsAssignedTeacher])
def create_timetable(request):
    user = request.user  # Get the requesting user
    class_id = request.data.get('class_id')
    timetable_entries = request.data.get('timetable_entries', [])

    try:
        class_instance = Class.objects.get(id=class_id)
    except Class.DoesNotExist:
        return Response({"error": "Class not found"}, status=status.HTTP_404_NOT_FOUND)

    # Ensure the requesting user belongs to the same school and campus as the class
    if class_instance.school_id != user.school_id or class_instance.campus_id != user.campus_id:
        return Response(
            {"error": "You can only create timetables for your assigned school and campus."},
            status=status.HTTP_403_FORBIDDEN
        )

    # Assign a default class for the 'Break' subject
    break_subject, _ = Subject.objects.get_or_create(
        name='Break',
        defaults={'class_id': class_instance}
    )

    created_entries = []  # Track created entries for response

    for entry in timetable_entries:
        subject_id = entry.get('subject')
        day = entry.get('day')
        start_time = entry.get('startTime')
        end_time = entry.get('endTime')

        subject_instance = break_subject if not subject_id else get_object_or_404(Subject, id=subject_id)

        # Retrieve the teacher if applicable
        teacher = None
        if subject_id:
            teacher_class = TeacherLevelClass.objects.filter(
                class_id=class_instance,
                subjects_taught=subject_instance
            ).first()
            teacher = teacher_class.teacher if teacher_class else None

        # Create the timetable entry with school and campus details
        timetable_entry = TimeTable.objects.create(
            school_id=user.school_id,  # Assign school ID
            campus_id=user.campus_id,  # Assign campus ID
            class_id=class_instance,
            subject=subject_instance,
            teacher=teacher,
            day=day,
            start_time=start_time,
            end_time=end_time,
        )

        created_entries.append({
            "class_id": class_instance.id,
            "school_id": user.school_id,
            "campus_id": user.campus_id,
            "subject": subject_instance.name,
            "teacher": teacher.username if teacher else None,
            "day": day,
            "start_time": start_time,
            "end_time": end_time,
        })

    return Response(
        {"message": "Timetable entries created successfully", "created_entries": created_entries},
        status=status.HTTP_201_CREATED
    )


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus])
def view_timetable(request, class_id):
    timetable = TimeTable.objects.filter(class_id=class_id)
    serializer = TimeTableSerializer(timetable, many=True)
    return Response(serializer.data)

@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated, IsAssignedTeacher])
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
@permission_classes([permissions.IsAuthenticated, IsAssignedTeacher])
def delete_timetable(request, pk):
    """Delete a specific timetable entry."""
    try:
        timetable = TimeTable.objects.get(pk=pk)
    except TimeTable.DoesNotExist:
        return Response({"error": "TimeTable entry not found."}, status=status.HTTP_404_NOT_FOUND)

    timetable.delete()
    return Response({"message": "TimeTable entry deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


class AssessmentNameListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdminInSchoolOrCampus]

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
    permission_classes = [IsTeacherOrAdminInSchoolOrCampus]  # Admins or assigned teachers can edit/delete

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
    permission_classes = [permissions.IsAuthenticated]  

    def get_permissions(self):
        """
        Assign different permissions based on the request method.
        """
        if self.request.method in ["GET"]:  # List and Retrieve
            return [permissions.IsAuthenticated(), IsRegisteredInSchoolOrCampus()]
        
        elif self.request.method in ["POST", "PUT", "PATCH"]:  # Create and Update
            return [permissions.IsAuthenticated(), IsTeacherOrAdminInSchoolOrCampus()]
        
        elif self.request.method == "DELETE":  # Delete
            return [permissions.IsAuthenticated(), IsTeacherOrAdminInSchoolOrCampus(), permissions.IsAdminUser()]
        
        return super().get_permissions()

    def get_queryset(self):
        """
        Filter levels to only those in the user's school/campus.
        """
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_superuser:  # Superusers see all
            if user.school:
                queryset = queryset.filter(school=user.school)
            if user.campus:
                queryset = queryset.filter(campus=user.campus)
        return queryset
    
    def get_object(self):
        """
        Optimize retrieval with select_related for school and campus.
        """
        queryset = self.get_queryset().select_related('school', 'campus')
        obj = generics.get_object_or_404(queryset, pk=self.kwargs['pk'])
        return obj
    
    def check_tenancy(self, instance):
        """
        Helper method to check if the instance belongs to the user's school/campus.
        Allows actions within the same school even if campus differs.
        """
        user = self.request.user
        school_id = self.request.auth.get('school_id') if self.request.auth else user.school_id
        campus_id = self.request.auth.get('campus_id') if self.request.auth else user.campus_id

        if school_id and instance.school_id != school_id:
            logger.warning(f"User {user} denied access to subject {instance.id} (school mismatch: {school_id} vs {instance.school_id})")
            return False
        
        # Granular campus check: Allow if school matches, even if campus differs
        if campus_id and instance.campus_id != campus_id:
            if instance.school_id != school_id:
                logger.warning(f"User {user} denied access to subject {instance.id} (campus mismatch: {campus_id} vs {instance.campus_id}, school mismatch)")
                return False
        
        return True

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
        """
        Update a level (full update) with tenancy enforcement.
        """
        instance = self.get_object()
        
        if not self.check_tenancy(instance) and not request.user.is_superuser:
            return Response({'error': 'You do not have permission to update this level'}, status=status.HTTP_403_FORBIDDEN)

        return self.update(request, *args, **kwargs)

    def patch(self, request, *args, **kwargs):
        """
        Update a level (partial update) with tenancy enforcement.
        """
        instance = self.get_object()
        
        if not self.check_tenancy(instance) and not request.user.is_superuser:
            return Response({'error': 'You do not have permission to update this level'}, status=status.HTTP_403_FORBIDDEN)

        return self.partial_update(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        """
        Delete a level with tenancy enforcement.
        """
        instance = self.get_object()
        
        if not self.check_tenancy(instance) and not request.user.is_superuser:
            return Response({'error': 'You do not have permission to delete this level'}, status=status.HTTP_403_FORBIDDEN)

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

    permission_classes = [permissions.IsAuthenticated]  

    def get_permissions(self):
        """
        Assign different permissions based on the request method.
        """
        if self.request.method in ["GET"]:  # List and Retrieve
            return [permissions.IsAuthenticated(), IsRegisteredInSchoolOrCampus()]
        
        elif self.request.method in ["POST", "PUT", "PATCH"]:  # Create and Update
            return [permissions.IsAuthenticated(), IsTeacherOrAdminInSchoolOrCampus()]
        
        elif self.request.method == "DELETE":  # Delete
            return [permissions.IsAuthenticated(), IsTeacherOrAdminInSchoolOrCampus(), permissions.IsAdminUser()]
        
        return super().get_permissions()
    
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