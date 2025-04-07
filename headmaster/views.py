from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from user_auth.models import User, Role
from student_performance.models import Student
from user_auth.permissions import IsHeadmaster, IsTeacher, IsRegisteredInSchoolOrCampus


class HeadMasterDashboardStatisticsView(APIView):
    permission_classes = [IsAuthenticated, IsRegisteredInSchoolOrCampus]  # Only allow authenticated users registered in the school/campus

    def get(self, request, *args, **kwargs):
        # Get the current user's school and campus
        user_school_id = request.user.school_id
        user_campus_id = request.user.campus_id

        # Filter users based on school and campus
        teachers = User.objects.filter(roles__name="Teacher", school_id=user_school_id, campus_id=user_campus_id)
        parents = User.objects.filter(roles__name="Parent", school_id=user_school_id, campus_id=user_campus_id)
        students = User.objects.filter(roles__name="Student", school_id=user_school_id, campus_id=user_campus_id)

        # Count teachers
        total_teachers = teachers.count()
        male_teachers = teachers.filter(gender='Male').count()
        female_teachers = teachers.filter(gender='Female').count()

        # Count parents
        total_parents = parents.count()
        male_parents = parents.filter(gender='Male').count()
        female_parents = parents.filter(gender='Female').count()

        # Count students
        total_students = students.count()
        male_students = students.filter(gender='Male').count()
        female_students = students.filter(gender='Female').count()

        # Prepare response data
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