from decimal import Decimal

from .models import ProcessedMarks, Assessment, Subject, ClassEnrollment
from .assign_grade import assign_grade

def calculate_processed_marks(class_id, semester, student):
    """
    Calculate and update ProcessedMarks for a student.
    """
    student_assessments = Assessment.objects.filter(
        student_id=student,
        class_id=class_id,
        semester=semester
    )

    total_score = Decimal(0)
    subject_data = []

    for subject in Subject.objects.all():
        assessments = student_assessments.filter(subject=subject)

        # Calculate scores (same as in your `ProcessedMarksView`)
        exercise_assignment_scores = assessments.filter(
            assessment_type__in=['Exercise', 'Assignment']
        ).order_by('-obtained_marks')[:4]

        exercise_assignment_total = sum([float(score.obtained_marks) for score in exercise_assignment_scores])
        exercise_assignment_score = (exercise_assignment_total / 80) * 20

        midterm = assessments.filter(assessment_type='MidTermExam').aggregate(total=Avg('obtained_marks'))['total'] or 0
        midterm_score = (float(midterm) / 100) * 30

        final_exam = assessments.filter(assessment_type='Final Exam').first()
        final_exam_score = (float(final_exam.obtained_marks) / float(final_exam.total_marks)) * 50 if final_exam else 0

        subject_score = exercise_assignment_score + midterm_score + final_exam_score
        total_score += Decimal(subject_score)

        grade = assign_grade(subject_score)

        subject_data.append({
            'subject_name': subject.name,
            'exercise_assignment_score': exercise_assignment_score,
            'midterm_score': midterm_score,
            'final_exam_score': final_exam_score,
            'total_subject_score': subject_score,
            'grade': grade
        })

    average_total_score = float(total_score / len(Subject.objects.all()))

    # Promotion status for "2nd Semester"
    status = 'promoted' if semester == "2nd Semester" and average_total_score >= 45 else 'repeated'

    # Update or create ProcessedMarks
    ProcessedMarks.objects.update_or_create(
        student=student,
        class_id=class_id,
        semester=semester,
        defaults={
            'total_score': average_total_score,
            'status': status,
            'subject_data': subject_data,  # Ensure JSON serializable
        }
    )
