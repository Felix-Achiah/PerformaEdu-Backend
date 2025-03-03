from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import User
from student_performance.models import TeacherLevelClass


class IsRole(BasePermission):
    def __init__(self, role):
        self.role = role

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_role(self.role)


class IsTeacher(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_role('Teacher')
    

class IsParent(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_role('Parent')


class IsStudent(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_role('Student')
    

class IsHeadmaster(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_role('Headmaster')


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_role('Admin')


class IsTeacherOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            (request.user.has_role('Teacher') or request.user.has_role('Admin'))
        )

class IsAssignedTeacher(BasePermission):
    def has_permission(self, request, view):
        # Allow GET for all authenticated users
        if request.method in SAFE_METHODS:
            return request.user.is_authenticated
        
        # For POST, PUT, DELETE, check if user is a teacher assigned to the class-subject
        if not request.user.is_authenticated:
            return False
        
        class_id = request.data.get('class_id')
        subject_id = request.data.get('subject')
        if not class_id or not subject_id:
            return False
        
        return TeacherLevelClass.objects.filter(
            teacher=request.user,
            class_id=class_id,
            subjects_taught=subject_id
        ).exists()

class IsAdminOrAssignedTeacher(BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.user.roles.filter(name='Admin').exists():  # Adjust based on your role setup
            return True
        return IsAssignedTeacher().has_permission(request, view)
























# def is_parent(user):
#     return user.user_type == User.PARENT

# def is_headmaster(user):
#     return user.user_type == User.HEADMASTER

# def is_teacher(user):
#     return user.user_type == User.TEACHER

# class IsParent(BasePermission):
#     def has_permission(self, request, view):
#         return is_parent(request.user)

# class IsHeadmaster(BasePermission):
#     def has_permission(self, request, view):
#         return is_headmaster(request.user)

# class IsTeacher(BasePermission):
#     def has_permission(self, request, view):
#         return is_teacher(request.user)
