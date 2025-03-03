from django.urls import path
from . import views

urlpatterns = [
    path('get-teachers-by-class/<int:class_id>/', views.get_teachers_by_class, name='get_teachers_by_class'),
    path('assign-main-teacher/', views.AssignMainTeacherView.as_view(), name='assign-main-teacher'),
    # Get Teacher's Performance in a subject per class
    path('get-teacher-performance/<int:class_id>/<int:subject_id>/', views.TeacherPerformanceView.as_view(), name='get-teachers-performance'),
    path('teachers/', views.TeacherListView.as_view(), name='teacher-list'),
]
