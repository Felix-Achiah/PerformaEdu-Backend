from django.urls import path
from . import views

urlpatterns = [
    path('get-class-info/<int:class_id>/', views.get_class_info, name='get-class-info'),
    path('get-class-performance/<int:class_id>/', views.get_class_performance, name='get-class-performance'),
    path('download-class-performance/<int:class_id>/', views.export_class_data, name='download-class-performance'),
]