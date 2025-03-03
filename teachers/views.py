from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Avg, F
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework.views import APIView
import logging

from user_auth.serializers import UserSerializer
from student_performance.serializers import TeacherLevelClassSerializer
from teachers.serializers import MainTeacherAssignmentSerializer
from user_auth.models import Role
from student_performance.models import TeacherLevelClass, Class, Subject, ClassEnrollment, HistoricalClassEnrollment, Assessment
from user_auth.permissions import IsAdmin, IsTeacherOrAdmin

logger = logging.getLogger(__name__)
User = get_user_model()

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_teachers_by_class(request, class_id):
    try:
        # Query to get the class information
        class_info = Class.objects.get(id=class_id)

        # Query to get all TeacherLevelClass instances for the given class_id
        teacher_classes = TeacherLevelClass.objects.filter(class_id=class_id)
        
        # Extract teacher IDs from the teacher_classes
        teacher_ids = teacher_classes.values_list('teacher', flat=True)
        
        # Query to get all users with user_type 'Teacher' and filter by the extracted teacher IDs
        teachers = User.objects.filter(user_type=User.TEACHER, id__in=teacher_ids)
        
        # Serialize the data
        serializer = UserSerializer(teachers, many=True)
        
        # Prepare the response data
        response_data = {
            'class_id': class_info.id,
            'class_name': class_info.name,
            'teachers': serializer.data
        }
        
        # Return the response
        return Response(response_data, status=status.HTTP_200_OK)
    except Exception as e:
        # Handle any exceptions that may occur
        return Response(data={'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class TeacherListView(APIView):
    permission_classes = [IsAuthenticated]  # Only authenticated users can access this view

    def get(self, request, *args, **kwargs):
        # Get the Role object for "Teacher"
        teacher_role = Role.objects.filter(name='Teacher').first()

        if not teacher_role:
            return Response({"error": "Teacher role does not exist."}, status=404)

        # Filter users with the "Teacher" role
        teachers = User.objects.filter(roles=teacher_role)

        # Serialize the queryset
        serializer = UserSerializer(teachers, many=True)

        # Return the serialized data
        return Response(serializer.data)
    

class AssignMainTeacherView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin | IsTeacherOrAdmin]

    def post(self, request, *args, **kwargs):
        class_id = request.data.get('class_id')
        teacher_id = request.data.get('teacher_id')
        is_main_teacher = request.data.get('is_main_teacher', False)  # Default to False

        if not class_id or not teacher_id:
            return Response({"error": "class_id and teacher_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Validate class and teacher existence
            class_obj = Class.objects.get(id=class_id)
            teacher = User.objects.get(id=teacher_id)

            # Check if user has 'Teacher' role (adjust based on your role setup)
            if not teacher.roles.filter(name='Teacher').exists():
                return Response({"error": "User is not a teacher."}, status=status.HTTP_400_BAD_REQUEST)

            # Check if the teacher-class assignment exists
            try:
                teacher_level_class, created = TeacherLevelClass.objects.get_or_create(
                    teacher=teacher,
                    class_id=class_obj,
                    defaults={'is_main_teacher': is_main_teacher}
                )
                serializer = MainTeacherAssignmentSerializer(teacher_level_class, data={'is_main_teacher': is_main_teacher}, partial=True)
            except TeacherLevelClass.DoesNotExist:
                # Create new assignment if it doesn’t exist
                teacher_level_class = TeacherLevelClass(teacher=teacher, class_id=class_obj, is_main_teacher=is_main_teacher)
                serializer = MainTeacherAssignmentSerializer(teacher_level_class, data={'is_main_teacher': is_main_teacher}, partial=True)
                created = True

            if serializer.is_valid():
                serializer.save()
                logger.info(f"Teacher {teacher.username} assigned to {class_obj.name}, Main: {is_main_teacher}")
                return Response({
                    "message": "Main teacher assigned successfully.",
                    "is_main_teacher": teacher_level_class.is_main_teacher
                }, status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Class.DoesNotExist:
            return Response({"error": "Class not found."}, status=status.HTTP_404_NOT_FOUND)
        except User.DoesNotExist:
            return Response({"error": "Teacher not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f"Error assigning main teacher: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class TeacherPerformanceView(APIView):

    def get(self, request, class_id, subject_id):
        try:
            # Find the teacher assigned to the class and subject
            teacher_level_class = TeacherLevelClass.objects.filter(class_id=class_id, subjects_taught=subject_id).first()
            if not teacher_level_class:
                return Response({"detail": "Teacher not found for the given class and subject"}, status=status.HTTP_404_NOT_FOUND)

            teacher = teacher_level_class.teacher

            # Fetch all academic years from both current and historical enrollments for this class
            academic_years = list(
                ClassEnrollment.objects.filter(class_id=class_id).values_list('academic_year', flat=True)
            ) + list(
                HistoricalClassEnrollment.objects.filter(class_enrolled=class_id).values_list('academic_year', flat=True)
            )

            # Fetch performance data for each academic year and both semesters, scaling to 100%
            performance_data = {}
            for academic_year in academic_years:
                assessments = Assessment.objects.filter(
                    class_id=class_id,
                    subject_id=subject_id,
                    teacher=teacher,
                    class_id__classenrollment__academic_year=academic_year
                ).values('semester').annotate(
                    average_score=Avg((F('obtained_marks') / F('total_marks')) * 100)
                )

                # Prepare structure to hold data for both semesters in each academic year
                performance_data[academic_year] = {
                    '1st Semester': None,
                    '2nd Semester': None,
                }

                for assessment in assessments:
                    semester = assessment['semester']
                    avg_score = assessment['average_score']
                    performance_data[academic_year][semester] = avg_score

            return Response({
                "teacher": teacher.username,
                "subject": Subject.objects.get(id=subject_id).name,
                "performance_data": performance_data
            }, status=status.HTTP_200_OK)

        except Class.DoesNotExist:
            return Response({"detail": "Class not found"}, status=status.HTTP_404_NOT_FOUND)
        except Subject.DoesNotExist:
            return Response({"detail": "Subject not found"}, status=status.HTTP_404_NOT_FOUND)