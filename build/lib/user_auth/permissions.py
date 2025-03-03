from rest_framework.permissions import BasePermission
from .models import User


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
