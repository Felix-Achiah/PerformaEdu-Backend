from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import generics, permissions, status
from django.shortcuts import get_object_or_404
from django.contrib.auth import get_user_model
import logging

from .models import AcademicYear
from student_performance.models import TeacherLevelClass, TeacherAssignmentHistory, Subject, Class, Student, StudentParentRelation, ClassEnrollment
from student_performance.serializers import TeacherLevelClassSerializer
from user_auth.models import User
from user_auth.serializers import UserSerializer
from .serializers import AssignSubjectsToTeachersSerializer, AcademicYearSerializer
from user_auth.permissions import IsAdmin, IsTeacherOrAdmin, IsTeacherOrAdminInSchoolOrCampus, IsRegisteredInSchoolOrCampus

User = get_user_model()
logger = logging.getLogger(__name__)

class AssignSubjectsToTeachersView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdminInSchoolOrCampus]
    def post(self, request, *args, **kwargs):
        if not isinstance(request.data, list):
            return Response(
                {"error": "Expected a list of assignments, but got an object."},
                status=status.HTTP_400_BAD_REQUEST
            )

        responses = []  # To store success messages or errors
        errors = False  # Flag to check if any errors occur

        for item in request.data:
            serializer = AssignSubjectsToTeachersSerializer(data=item)
            if serializer.is_valid():
                teacher = serializer.validated_data['teacher']
                class_id = serializer.validated_data['class_id']
                subjects_taught = serializer.validated_data['subjects_taught']
                is_main_teacher = serializer.validated_data.get('is_main_teacher', False)

                # Check if the teacher is already assigned to the class
                teacher_level_class, created = TeacherLevelClass.objects.get_or_create(
                    teacher=teacher,
                    class_id=class_id,
                    defaults={'is_main_teacher': is_main_teacher}
                )

                # Add subjects to the teacher's subjects_taught
                teacher_level_class.subjects_taught.set(subjects_taught)

                # Save initial assignment to history (only if newly created)
                if created:
                    history_record = TeacherAssignmentHistory.objects.create(
                        teacher=teacher,
                        class_id=class_id
                    )
                    history_record.subjects_taught.set(subjects_taught)
                    history_record.save()

                # If the teacher is being set as the main teacher, ensure no other main teacher exists for the class
                if is_main_teacher:
                    TeacherLevelClass.objects.filter(
                        class_id=class_id, is_main_teacher=True
                    ).exclude(id=teacher_level_class.id).update(is_main_teacher=False)

                responses.append({"message": "Subjects assigned successfully.", "data": serializer.data})
            else:
                errors = True
                responses.append({"error": serializer.errors})

        return Response(
            responses,
            status=status.HTTP_400_BAD_REQUEST if errors else status.HTTP_201_CREATED
        )


class TeacherSubjectsByClassView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus]
    def get(self, request, class_id):
        try:
            # Fetch all TeacherLevelClass records for the given class_id
            teacher_level_classes = TeacherLevelClass.objects.filter(class_id=class_id)
            
            # Serialize the data
            serializer = TeacherLevelClassSerializer(teacher_level_classes, many=True)
            
            # Return the serialized data
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        except Exception as e:
            # Handle any errors
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    

class UpdateTeacherSubjectsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdminInSchoolOrCampus]

    def put(self, request, *args, **kwargs):
        teacher_id = request.data.get("teacher_id")
        class_id = request.data.get("class_id")
        subjects = request.data.get("subjects", [])

        if not teacher_id or not class_id:
            return Response(
                {"error": "Teacher ID and Class ID are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Retrieve the TeacherLevelClass instance
        teacher_level_class = get_object_or_404(
            TeacherLevelClass, teacher_id=teacher_id, class_id=class_id
        )

        if not subjects:
            # Save current assignment to history before unassigning
            history_record = TeacherAssignmentHistory.objects.create(
                teacher=teacher_level_class.teacher,
                class_id=teacher_level_class.class_id
            )
            history_record.subjects_taught.set(teacher_level_class.subjects_taught.all())
            history_record.save()
            # If no subjects provided, delete the record (unassign teacher from class)
            teacher_level_class.delete()

            return Response(
                {"message": "Teacher unassigned from all subjects, history saved."},
                status=status.HTTP_200_OK,
            )
        else:
            # Update subjects as usual
            teacher_level_class.subjects_taught.set(subjects)
            teacher_level_class.save()
            return Response(
                {"message": "Subjects updated successfully."},
                status=status.HTTP_200_OK,
            )
        

# Create and List Academic Years
class AcademicYearListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        """
        Assign different permissions based on the request method.
        """
        if self.request.method in ["GET"]:  # List and Retrieve
            return [permissions.IsAuthenticated(), IsRegisteredInSchoolOrCampus()]
        
        elif self.request.method in ["POST"]:  # Create
            return [permissions.IsAuthenticated(), IsTeacherOrAdminInSchoolOrCampus()]
        
        return super().get_permissions()

    def get(self, request):
        academic_years = AcademicYear.objects.all()
        serializer = AcademicYearSerializer(academic_years, many=True)
        return Response(serializer.data)

    def post(self, request):
        # Check if the request contains a list (bulk create) or a single object
        is_bulk = isinstance(request.data, list)
        
        serializer = AcademicYearSerializer(data=request.data, many=is_bulk)

        # ✅ Call is_valid() before accessing validated_data
        if serializer.is_valid():
            active_set = False  # To track if an active year has already been set

            # Now it's safe to access validated_data
            validated_data = serializer.validated_data
            if not isinstance(validated_data, list):
                validated_data = [validated_data]

            for academic_year_data in validated_data:
                if academic_year_data.get('is_active', False):
                    if not active_set:
                        # Deactivate existing active years only once
                        AcademicYear.objects.filter(is_active=True).update(is_active=False)
                        active_set = True
                    else:
                        # Prevent multiple active academic years in the same bulk request
                        return Response(
                            {"error": "Only one academic year can be active at a time."},
                            status=status.HTTP_400_BAD_REQUEST
                        )

            # Save all instances
            serializer.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ActiveAcademicYearView(generics.RetrieveAPIView):
    """
    A view to fetch the currently active academic year for the user's school and campus.
    Returns a single object or 404 if no active year exists.
    """
    permission_classes = [permissions.IsAuthenticated, IsRegisteredInSchoolOrCampus]
    serializer_class = AcademicYearSerializer

    def get_object(self):
        # Get the current user's school and campus
        user_school_id = self.request.user.school_id
        user_campus_id = self.request.user.campus_id

        try:
            # Fetch the active academic year for the user's school and campus
            return AcademicYear.objects.get(
                is_active=True, 
                school_id=user_school_id, 
                campus_id=user_campus_id
            )
        except AcademicYear.DoesNotExist:
            raise NotFound("No active academic year found for your school and campus.")
        except AcademicYear.MultipleObjectsReturned:
            # If multiple active years exist, return the most recent one
            return AcademicYear.objects.filter(
                is_active=True, 
                school_id=user_school_id, 
                campus_id=user_campus_id
            ).order_by('-start_date').first()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)



# Retrieve, Update, Delete Academic Year
class AcademicYearDetailView(APIView):
    """
    API view to retrieve, update, and delete academic years,
    ensuring that users can only manage academic years linked to their school and campus.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get_permissions(self):
        """
        Assign different permissions based on the request method.
        """
        if self.request.method == "GET":  # Retrieve
            return [permissions.IsAuthenticated(), IsRegisteredInSchoolOrCampus()]
        
        elif self.request.method in ["PUT", "PATCH"]:  # Update
            return [permissions.IsAuthenticated(), IsTeacherOrAdminInSchoolOrCampus()]
        
        elif self.request.method == "DELETE":  # Delete
            return [permissions.IsAuthenticated(), IsTeacherOrAdminInSchoolOrCampus()]
        
        return super().get_permissions()

    def get_object(self, pk):
        """
        Fetch the academic year, ensuring it belongs to the user's school and campus.
        """
        user = self.request.user
        return get_object_or_404(
            AcademicYear, 
            pk=pk, 
            school_id=user.school_id, 
            campus_id=user.campus_id
        )

    def get(self, request, pk):
        academic_year = self.get_object(pk)
        serializer = AcademicYearSerializer(academic_year)
        return Response(serializer.data)

    def put(self, request, pk):
        academic_year = self.get_object(pk)
        serializer = AcademicYearSerializer(academic_year, data=request.data)

        if serializer.is_valid():
            # Ensure only one active academic year per school and campus
            if serializer.validated_data.get('is_active', False):
                AcademicYear.objects.filter(
                    is_active=True, 
                    school_id=request.user.school_id, 
                    campus_id=request.user.campus_id
                ).exclude(id=pk).update(is_active=False)

            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        """
        Set a specific academic year as active and deactivate others in the same school and campus.
        """
        academic_year = self.get_object(pk)

        # Deactivate all active years in the same school and campus
        AcademicYear.objects.filter(
            is_active=True, 
            school_id=request.user.school_id, 
            campus_id=request.user.campus_id
        ).update(is_active=False)
        
        # Activate the selected academic year
        academic_year.is_active = True
        academic_year.save()

        return Response(
            {"success": f"Academic Year {academic_year.start_year}/{academic_year.end_year} is now active."}, 
            status=status.HTTP_200_OK
        )

    def delete(self, request, pk):
        """
        Delete an academic year, ensuring it's within the user's school and campus.
        """
        academic_year = self.get_object(pk)
        academic_year.delete()
        return Response({"success": "Academic Year deleted successfully."}, status=status.HTTP_204_NO_CONTENT)
    

class ParentsByClassView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin | IsAdmin]
    def get(self, request, class_id):
        # Get all students enrolled in the specified class
        student_enrollments = ClassEnrollment.objects.filter(class_id=class_id).select_related('student')
        students = [enrollment.student for enrollment in student_enrollments]

        if not students:
            return Response({"message": "No students found for this class."}, status=status.HTTP_404_NOT_FOUND)
        
        # Get all parent-student relations for these students
        relations = StudentParentRelation.objects.filter(student__in=students).select_related('parent', 'student')
        
        # Structure the response data
        data = {}
        for relation in relations:
            parent = relation.parent
            student = relation.student
            
            parent_info = {
                "parent_id": parent.id,
                "parent_name": parent.username,
                "profile_pic": parent.profile_picture.url if parent.profile_picture else None,
                "email": parent.email,
                "phone": parent.phone,
            }
            
            student_info = {
                "student_id": student.id,
                "student_name": student.name,
                "profile_pic": student.student_profile_pic.url if student.student_profile_pic else None,
            }
            
            # Group children under the parent
            if parent.id not in data:
                data[parent.id] = {
                    **parent_info,
                    "children": [student_info]
                }
            else:
                data[parent.id]["children"].append(student_info)

        return Response(list(data.values()), status=status.HTTP_200_OK)
    
class ParentsView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin | IsAdmin]
    def get(self, request):
        # Fetch all users with the 'Parent' role
        parents = User.objects.filter(roles__name='Parent')

        print()

        if not parents.exists():
            return Response({"message": "No parents found."}, status=status.HTTP_404_NOT_FOUND)

        # Structure the response data
        data = []
        for parent in parents:
            parent_info = {
                "id": parent.id,
                "name": parent.username,
                "profile_pic": parent.profile_picture.url if parent.profile_picture else None,
                "email": parent.email,
                "phone": parent.phone,
                "is_active": parent.is_active,
                "children": []
            }

            # Fetch children associated with this parent
            relations = StudentParentRelation.objects.filter(parent=parent).select_related('student')
            for relation in relations:
                student = relation.student
                student_info = {
                    "student_id": student.id,
                    "student_name": student.username,
                    "profile_pic": student.profile_picture.url if student.profile_picture else None,
                }
                parent_info["children"].append(student_info)

            data.append(parent_info)

        return Response(data, status=status.HTTP_200_OK)

# 
class TeacherListView(generics.ListAPIView):
    """
    API view to list all users who have the role of 'Teacher'.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(roles__name="Teacher")


class StudentListView(generics.ListAPIView):
    """
    API view to list all users who have the role of 'Student'.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return User.objects.filter(roles__name="Student")


# Update User Details
class UpdateUserView(generics.UpdateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin | IsAdmin]

    def update(self, request, *args, **kwargs):
        user_id = request.data.get('id')  # Extract user ID from request payload
        
        if not user_id:
            return Response({"error": "User ID is required in the request body"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        serializer = self.get_serializer(user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

# Delete a user account
class DeleteUserView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin | IsAdmin]

    def delete(self, request, *args, **kwargs):
        user_id = request.data.get("id")  # Extract user ID from request body

        if not user_id:
            return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if the user is deleting their own account or is an admin
        if request.user.id == user.id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        user.delete()
        return Response({"message": "User account deleted successfully"}, status=status.HTTP_200_OK)
    

# Suspend User Account
class SuspendUserView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin | IsAdmin]

    def patch(self, request, *args, **kwargs):
        user_id = request.data.get("id")

        if not user_id:
            return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if the user is suspending their own account or is an admin
        if request.user.id == user.id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        user.is_active = False  # Suspend the user
        user.save()

        return Response({"message": "User account has been suspended"}, status=status.HTTP_200_OK)


# Suspend User Account
class ActivateUserView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTeacherOrAdmin | IsAdmin]

    def patch(self, request, *args, **kwargs):
        user_id = request.data.get("id")  # Extract user ID from request body

        if not user_id:
            return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        # Check if the user is suspending their own account or is an admin
        if request.user.id == user.id:
            return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

        user.is_active = True  # Suspend the user
        user.save()

        return Response({"message": "User account has been activated"}, status=status.HTTP_200_OK)


