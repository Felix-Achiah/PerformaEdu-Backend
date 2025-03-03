from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from user_auth.models import User, Role
from student_performance.models import Student
from user_auth.permissions import IsHeadmaster, IsTeacher


class HeadMasterDashboardStatisticsView(APIView):
    permission_classes = [IsAuthenticated | IsHeadmaster | IsTeacher]  # Ensure only authenticated users can access this view

    def get(self, request, *args, **kwargs):
        # Get the Role objects for Teacher and Parent
        teacher_role = Role.objects.filter(name='Teacher').first()
        parent_role = Role.objects.filter(name='Parent').first()

        # Count the number of teachers
        total_teachers = User.objects.filter(roles=teacher_role).count()

        # Count male and female teachers
        male_teachers = User.objects.filter(roles=teacher_role, gender='Male').count()
        female_teachers = User.objects.filter(roles=teacher_role, gender='Female').count()

        # Count the number of parents
        total_parents = User.objects.filter(roles=parent_role).count()

        # Count male and female parents
        male_parents = User.objects.filter(roles=parent_role, gender='Male').count()
        female_parents = User.objects.filter(roles=parent_role, gender='Female').count()

        # Count the total number of students
        total_students = Student.objects.count()

        # Count male and female students
        male_students = Student.objects.filter(gender='Male').count()
        female_students = Student.objects.filter(gender='Female').count()

        # Prepare the response data
        data = {
            'teachers': {
                'total': total_teachers,
                'male': male_teachers,
                'female': female_teachers,
            },
            'parents': {
                'total': total_parents,
                'male': male_parents,
                'female': female_parents,
            },
            'students': {
                'total': total_students,
                'male': male_students,
                'female': female_students,
            },
        }

        return Response(data)

