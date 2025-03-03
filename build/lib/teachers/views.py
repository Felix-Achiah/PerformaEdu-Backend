from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Avg, F
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework.views import APIView

from user_auth.serializers import UserSerializer
from student_performance.serializers import TeacherLevelClassSerializer
from teachers.serializers import MainTeacherAssignmentSerializer
from student_performance.models import TeacherLevelClass, Class, Subject, ClassEnrollment, HistoricalClassEnrollment, Assessment


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


class AssignMainTeacherView(APIView):
    def post(self, request, *args, **kwargs):
        class_id = request.data.get('class_id')
        teacher_id = request.data.get('teacher_id')
        
        try:
            # Fetch the TeacherLevelClass entry for the teacher and class
            teacher_level_class = TeacherLevelClass.objects.get(class_id=class_id, teacher_id=teacher_id)
            
            # Serialize the data with the is_main_teacher flag
            serializer = MainTeacherAssignmentSerializer(teacher_level_class, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response({"message": "Main teacher assigned successfully."}, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        except TeacherLevelClass.DoesNotExist:
            return Response({"error": "Teacher or class not found."}, status=status.HTTP_404_NOT_FOUND)
        

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