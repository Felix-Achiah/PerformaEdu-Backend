import pandas as pd
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status, permissions
from django.db.models import Avg, Count, Q
from io import BytesIO
import uuid
import os
import mimetypes
from django.http import FileResponse
from django.core.exceptions import ObjectDoesNotExist

from user_auth.permissions import IsHeadmaster, IsTeacher
from student_performance.models import ClassEnrollment, Assessment, TeacherLevelClass

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsTeacher | IsHeadmaster])
def get_class_info(request, class_id):
    try:
        # Fetch class info and the main teacher
        main_teacher = TeacherLevelClass.objects.filter(class_id=class_id, is_main_teacher=True).first()

        # Get the student details
        students = ClassEnrollment.objects.filter(class_id=class_id)
        male_students = students.filter(student__gender='Male').count()
        female_students = students.filter(student__gender='Female').count()
        total_students = students.count()

        # Prepare response data
        data = {
            'main_teacher': main_teacher.teacher.username if main_teacher else None,  # Main teacher's name
            'male_students': male_students,
            'female_students': female_students,
            'total_students': total_students
        }
        return Response(data)
    except TeacherLevelClass.DoesNotExist:
        return Response({"error": "Class not found"}, status=404)

@api_view(['GET'])
def get_class_performance(request, class_id):
    try:
        # Get class assessments
        assessments = Assessment.objects.filter(class_id=class_id)
        
        # Average performance across subjects
        avg_performance = assessments.values('subject__name').annotate(avg_score=Avg('obtained_marks'))
        
        # Top performers (students with average score > 85)
        top_performers = assessments.values('student_id', 'student_id__name').annotate(avg_score=Avg('obtained_marks')).filter(avg_score__gt=85).order_by('-avg_score')
        
        # Grade distribution
        grade_distribution = assessments.values('subject__name').annotate(
            A_grade=Count('obtained_marks', filter=Q(obtained_marks__gte=80)),
            B_grade=Count('obtained_marks', filter=Q(obtained_marks__gte=70, obtained_marks__lt=80)),
            C_grade=Count('obtained_marks', filter=Q(obtained_marks__gte=60, obtained_marks__lt=70)),
            D_grade=Count('obtained_marks', filter=Q(obtained_marks__gte=50, obtained_marks__lt=60)),
            F_grade=Count('obtained_marks', filter=Q(obtained_marks__lt=50)),
        )
        
        return Response({
            'average_performance': avg_performance,
            'top_performers': top_performers,
            'grade_distribution': grade_distribution
        })
    except Assessment.DoesNotExist:
        return Response({"error": "Data not found"}, status=404)

@api_view(['GET'])
def export_class_data(request, class_id):
    try:
        # Fetching the data to export
        assessments = Assessment.objects.filter(class_id=class_id).values(
            'student_id__name', 'subject__name', 'assessment_type', 'obtained_marks', 'total_marks'
        )
        df = pd.DataFrame(assessments) 
        
        # Convert to Excel
        file_path = f'class_{class_id}_performance.xlsx'
        df.to_excel(file_path, index=False)
        
        with open(file_path, 'rb') as f:
            response = Response(f.read(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = f'attachment; filename={file_path}'
            return response
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['GET'])
def export_class_data(request, class_id):
    try:
        # Fetching the data to export
        assessments = Assessment.objects.filter(class_id=class_id).values(
            'student_id__name', 'subject__name', 'assessment_type', 'obtained_marks', 'total_marks'
        )
        
        file_path = generate_excel_file(assessments)
        
        with open(file_path, 'rb') as f:
            mime_type, _ = mimetypes.guess_type(file_path)
            response = FileResponse(f, content_type=mime_type)
            response['Content-Disposition'] = f'attachment; filename={os.path.basename(file_path)}'
            return response
    
    except ObjectDoesNotExist:
        return Response({"error": "Assessment not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
    
    finally:
        # Remove the generated file
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)

def generate_excel_file(assessments):
    """Generate Excel file from assessments data"""
    df = pd.DataFrame(assessments)
    file_path = f"{uuid.uuid4()}.xlsx"
    df.to_excel(file_path, index=False)
    return file_path