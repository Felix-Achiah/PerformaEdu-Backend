from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from user_auth.models import User, Role
from student_performance.models import Student
from user_auth.permissions import IsHeadmaster, IsTeacher


class HeadMasterDashboardStatisticsView(APIView):
    permission_classes = [IsAuthenticated | IsHeadmaster | IsTeacher]  # Ensure only authenticated users can access this view

    def get(self, request, *args, **kwargs):
        # Get the Role objects for Teacher
        teacher_role = Role.objects.filter(name='Teacher').first()

        # Count the number of teachers
        teacher_count = User.objects.filter(roles=teacher_role).count()

        # Count the total number of students
        total_students = Student.objects.count()

        # Count the number of male students
        male_students = Student.objects.filter(gender='Male').count()

        # Count the number of female students
        female_students = Student.objects.filter(gender='Female').count()

        # Prepare the response data
        data = {
            'total_teachers': teacher_count,
            'total_students': total_students,
            'male_students': male_students,
            'female_students': female_students,
        }

        return Response(data)
