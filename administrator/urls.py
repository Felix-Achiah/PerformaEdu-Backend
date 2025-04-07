from django.urls import path

from .views import AssignSubjectsToTeachersView, UpdateTeacherSubjectsView, TeacherSubjectsByClassView, AcademicYearListCreateView, AcademicYearDetailView, ParentsByClassView, ParentsView, UpdateUserView, DeleteUserView, SuspendUserView, ActivateUserView, TeacherListView, StudentListView, ActiveAcademicYearView

urlpatterns = [
    path('assign-subjects-to-teachers/', AssignSubjectsToTeachersView.as_view(), name='assign-subjects-to-teachers'),
    path('update-teacher-subjects/', UpdateTeacherSubjectsView.as_view(), name='update-teacher-subjects'),
    path('teacher-subjects/<uuid:class_id>/', TeacherSubjectsByClassView.as_view(), name='teacher-subjects-by-class'),

    path('academic-years/', AcademicYearListCreateView.as_view(), name='academic-year-list-create'),
    path('active-academic-year/', ActiveAcademicYearView.as_view(), name='active_academic_year'),
    path('academic-years/<uuid:pk>/', AcademicYearDetailView.as_view(), name='academic-year-detail'),

    path('parents-by-class/<uuid:class_id>/', ParentsByClassView.as_view(), name='parents_by_class'),

    path('parents/', ParentsView.as_view(), name='parents'),
    path('teachers/', TeacherListView.as_view(), name='teacher-list'),
    path('students/', StudentListView.as_view(), name='student-list'),

    # Update User Info
    path('users/update/', UpdateUserView.as_view(), name='update-user'),
    # Delete User Account
    path('users/delete/', DeleteUserView.as_view(), name='delete-user'),
    # Suspend User Account
    path('users/suspend/', SuspendUserView.as_view(), name='suspend-user'),
    # Activate User Account
    path('users/activate/', ActivateUserView.as_view(), name='activate-user'),
]