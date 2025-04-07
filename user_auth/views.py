import datetime
import logging
import random
import jwt
import string
import pandas as pd
from django.urls import reverse
from django.utils.crypto import get_random_string
from django.conf import settings
from django.core.exceptions import FieldError, ObjectDoesNotExist
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core.mail import send_mail, EmailMultiAlternatives
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import update_session_auth_hash, get_user_model
from django.contrib.auth.hashers import make_password, check_password
from rest_framework.decorators import api_view, permission_classes, authentication_classes, renderer_classes, parser_classes
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.views import APIView
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.parsers import MultiPartParser
from rest_framework_simplejwt.exceptions import TokenError
from smtplib import SMTPException
from django.db.models import Q
from django.db import transaction

from .models import User, Role
from school.models import School, Campus
from .serializers import UserSerializer, PasswordResetSerializer, RoleSerializer
from student_performance.serializers import TeacherLevelClassSerializer, StudentSerializer, ClassEnrollment, HistoricalClassEnrollment, Class, StudentParentRelationSerializer
from student_performance.models import TeacherLevelClass, Student, StudentParentRelation, ClassEnrollment, HistoricalClassEnrollment, Class
from administrator.models import AcademicYear
from .tokens import create_jwt_pair_for_user
from .utils import generate_verification_token
from .permissions import IsAdmin, IsTeacherOrAdmin

logger = logging.getLogger(__name__)

# Register new user
def generate_default_password(length=12):
    """Generate a random default password."""
    characters = string.ascii_letters + string.digits + string.punctuation
    return ''.join(random.choice(characters) for _ in range(length))

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def sign_up(request):
    try:
        data = request.data
        users_data = data if isinstance(data, list) else [data]  # Handle single or multiple users
        created_users = []
        skipped_users = []

        for user_data in users_data:
            email = user_data.get('email')
            username = user_data.get('username')
            role_names = user_data.get('roles', [])
            school_name = user_data.get('school_name')  # Extract school name
            campus_name = user_data.get('campus_name')  # Extract campus name
            if isinstance(role_names, str):
                role_names = [role_names]

            # Check if user already exists by email or username
            existing_user = User.objects.filter(email=email).first() or User.objects.filter(username=username).first()
            if existing_user:
                skipped_users.append({'email': email, 'username': username, 'reason': 'User already exists'})
                continue

            # Fetch School and Campus IDs based on names
            school = None
            campus = None
            if school_name:
                try:
                    school = School.objects.get(name=school_name)
                except School.DoesNotExist:
                    skipped_users.append({
                        'email': email,
                        'username': username,
                        'reason': f"School '{school_name}' not found"
                    })
                    continue

            if campus_name:
                try:
                    campus = Campus.objects.get(name=campus_name, school=school if school else None)
                except Campus.DoesNotExist:
                    skipped_users.append({
                        'email': email,
                        'username': username,
                        'reason': f"Campus '{campus_name}' not found" + (f" in school '{school_name}'" if school else "")
                    })
                    continue

            # Validate roles
            roles = Role.objects.filter(name__in=role_names)
            if not roles.exists() and role_names:
                skipped_users.append({
                    'email': email,
                    'username': username,
                    'reason': f"Roles {role_names} not found"
                })
                continue

            # Generate a default password
            default_password = generate_default_password()

            with transaction.atomic():
                # Create the user with school and campus IDs
                user = User.objects.create(
                    email=email,
                    username=username,
                    password=make_password(default_password),
                    phone=user_data.get('phone'),
                    gender=user_data.get('gender'),
                    location=user_data.get('location'),
                    passcode=default_password,  # Store plain password
                    school=school,  # Assign School instance
                    campus=campus   # Assign Campus instance
                )
                user.roles.set(roles)
                user.save()
                created_users.append(user)

            # Log success
            logger.info(f"User '{email}' created with school '{school_name}' and campus '{campus_name}'")

            # Send default password to email (optional)
            # Example: send_email(user.email, "Your Password", f"Your default password is: {default_password}")

        # Serialize the created users
        serializer = UserSerializer(created_users, many=True)
        response_data = {
            'created_users': serializer.data,
            'skipped_users': skipped_users,
            'message': f'{len(created_users)} user(s) created successfully.'
        }

        return Response(data=response_data, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.error(f"Error in sign_up: {str(e)}")
        return Response(data={'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class RegisterStudentsAndParentsView(APIView):
    permission_classes = [permissions.IsAuthenticated | IsTeacherOrAdmin | IsAdmin]
    """
    API view to register one or multiple students and their parents at the same time.
    This also creates class enrollment, historical enrollment, and parent-student relationships.
    """

    def post(self, request):
        try:
            with transaction.atomic():
                data = request.data
                users_created = []
                users_skipped = []
                relationships_created = []

                # If the request contains a single object, wrap it in a list
                if isinstance(data, dict):
                    data = [data]  

                for entry in data:
                    parent_data = entry.get('parent', {})
                    student_data = entry.get('student', {})
                    school_name = entry.get('school_name')  # Extract school name
                    campus_name = entry.get('campus_name')  # Extract campus name

                    if not parent_data or not student_data:
                        return Response(
                            {"error": "Both parent and student data are required."},
                            status=status.HTTP_400_BAD_REQUEST,
                        )

                    # Check if parent already exists (by email or username)
                    parent_email = parent_data.get('email')
                    parent_email = parent_email.lower() if parent_email else ''
                    parent_username = parent_data.get('username', '')

                    existing_parent = User.objects.filter(
                        email=parent_email
                    ).first() if parent_email else User.objects.filter(
                        username=parent_username
                    ).first()

                    # Check if student already exists (by email or username)
                    student_email = student_data.get('email')
                    student_email = student_email.lower() if student_email else ''
                    student_username = student_data.get('username', '')
                    academic_year = student_data.get('academic_year', '')
                    # Fetch the academic year object
                    if academic_year:
                        academic_year_obj = AcademicYear.objects.filter(start_year=academic_year).first()
                        if not academic_year_obj:
                            users_skipped.append({
                                "student": {"email": student_email, "username": student_username},
                                "reason": f"Academic year '{academic_year}' does not exist"
                            })
                            continue  # Skip if academic year not found
                    else:
                        academic_year_obj = None

                    existing_student = User.objects.filter(
                        email=student_email
                    ).first() if student_email else User.objects.filter(
                        username=student_username
                    ).first()

                    if existing_parent and existing_student:
                        users_skipped.append({
                            "parent": {"email": parent_email, "username": parent_username},
                            "student": {"email": student_email, "username": student_username},
                            "reason": "Both parent and student already exist"
                        })
                        continue  # Skip this pair
                    
                    # Fetch School and Campus IDs based on names
                    school = None
                    campus = None
                    if school_name:
                        try:
                            school = School.objects.get(name=school_name)
                        except School.DoesNotExist:
                            users_skipped.append({
                                'parent': {"email": parent_email, "username": parent_username},
                                'student': {"email": student_email, "username": student_username},
                                'reason': f"School '{school_name}' not found"
                            })
                            continue
                    
                    if campus_name:
                        try:
                            campus = Campus.objects.get(name=campus_name, school=school if school else None)
                        except Campus.DoesNotExist:
                            users_skipped.append({
                                'parent': {"email": parent_email, "username": parent_username},
                                'student': {"email": student_email, "username": student_username},
                                'reason': f"Campus '{campus_name}' not found" + (f" in school '{school_name}'" if school else "")
                            })
                            continue

                    # Generate a default password for both parent & student
                    default_password = get_random_string(8)

                    # CREATE PARENT USER (if not exists)
                    if not existing_parent:
                        with transaction.atomic():
                            parent = User.objects.create(
                                email=parent_email if parent_email else None,
                                username=parent_username,
                                phone=parent_data.get('phone'),
                                passcode=default_password,  # Store plain password
                                password=make_password(default_password),  # Store hashed password
                                gender=parent_data.get('gender'),
                                location=parent_data.get('location'),
                                school=school,
                                campus=campus 
                            )
                            parent_role, _ = Role.objects.get_or_create(name="Parent")
                            parent.roles.add(parent_role)
                    else:
                        parent = existing_parent

                    # CREATE STUDENT USER (if not exists)
                    if not existing_student:
                        with transaction.atomic():
                            student = User.objects.create(
                                email=student_email if student_email else None,
                                username=student_username,
                                phone=student_data.get('phone'),
                                passcode=default_password,
                                password=make_password(default_password),
                                gender=student_data.get('gender'),
                                location=student_data.get('location'),
                                school=school,
                                campus=campus
                            )
                            student_role, _ = Role.objects.get_or_create(name="Student")
                            student.roles.add(student_role)
                    else:
                        student = existing_student

                    # HANDLE CLASS ENROLLMENT (Only for new students)
                    if not existing_student:
                        class_id = student_data.get('class_id')
                        academic_year = student_data.get('academic_year')

                        if class_id:
                            # Check if the student was previously enrolled
                            current_enrollment = ClassEnrollment.objects.filter(
                                student=student, status='existing'
                            ).first()

                            if current_enrollment:
                                # Move the existing record to historical enrollment
                                HistoricalClassEnrollment.objects.create(
                                    student=student,
                                    class_enrolled=current_enrollment.class_id,
                                    academic_year=current_enrollment.academic_year,
                                )
                                # Update previous enrollment status
                                current_enrollment.status = 'promoted'
                                current_enrollment.save()

                            # Enroll the student in the new class
                            new_class = Class.objects.get(id=class_id)
                            ClassEnrollment.objects.create(
                                student=student,
                                class_id=new_class,
                                academic_year=academic_year_obj,
                                status='existing'
                            )

                    # CREATE STUDENT-PARENT RELATIONSHIP
                    student_parent_relation, created = StudentParentRelation.objects.get_or_create(
                        student=student, parent=parent
                    )

                    if created:
                        relationships_created.append(StudentParentRelationSerializer(student_parent_relation).data)

                    # SEND EMAILS (if email exists)
                    # if not existing_parent and parent_email:
                    #     send_mail(
                    #         "Welcome to Our School Platform",
                    #         f"Hello {parent.username},\n\n"
                    #         f"Your account has been created successfully.\n"
                    #         f"Login Email: {parent.email}\n"
                    #         f"Temporary Password: {default_password}\n\n"
                    #         "Please change your password after logging in.",
                    #         settings.DEFAULT_FROM_EMAIL,
                    #         [parent.email],
                    #         fail_silently=True,
                    #     )

                    # if not existing_student and student_email:
                    #     send_mail(
                    #         "Welcome to Our School Platform",
                    #         f"Hello {student.username},\n\n"
                    #         f"Your account has been created successfully.\n"
                    #         f"Login Email: {student.email}\n"
                    #         f"Temporary Password: {default_password}\n\n"
                    #         "Please change your password after logging in.",
                    #         settings.DEFAULT_FROM_EMAIL,
                    #         [student.email],
                    #         fail_silently=True,
                    #     )

                    # Store created users for response
                    users_created.append({
                        "parent": UserSerializer(parent).data,
                        "student": UserSerializer(student).data
                    })

                return Response(
                    {
                        "message": "Students and parents registered successfully",
                        "users_created": users_created,
                        "users_skipped": users_skipped,
                        "relationships_created": relationships_created,
                    },
                    status=status.HTTP_201_CREATED,
                )

        except Exception as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsAdmin])
@parser_classes([MultiPartParser])
def bulk_user_upload(request):
    try:
        if 'file' not in request.FILES:
            return Response(data={'error': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES['file']
        if not file.name.endswith('.xlsx'):
            return Response(data={'error': 'File must be an Excel file (.xlsx).'}, status=status.HTTP_400_BAD_REQUEST)

        # Read the Excel file
        df = pd.read_excel(file)

        # Convert all column names to lowercase
        df.columns = df.columns.str.lower()

        required_columns = ['email', 'username', 'phone', 'gender', 'location', 'roles', 'school_name', 'campus_name']
        if not all(column in df.columns for column in required_columns):
            return Response(
                data={'error': f'File must contain the following columns: {required_columns}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_users = []
        skipped_users = []

        for _, row in df.iterrows():
            email = row['email']
            username = row['username']

            # Check if user already exists by email or username
            existing_user = User.objects.filter(email=email).first() or User.objects.filter(username=username).first()
            if existing_user:
                skipped_users.append({'email': email, 'username': username, 'reason': 'User already exists'})
                continue

            # Generate a default password
            default_password = generate_default_password()

            # Create the user
            user = User.objects.create(
                email=email,
                username=username,
                password=make_password(default_password),
                phone=row['phone'],
                gender=row['gender'],
                location=row['location'],
                passcode=default_password,  # Store plain password
                school=row['school_name'],
                campus=row['campus_name']
            )

            # Assign roles properly
            if isinstance(row['roles'], str):  
                roles = [role.strip() for role in row['roles'].split(',')]  # Split and remove extra spaces
                print(f"Extracted roles: {roles}")  # Debugging
            elif isinstance(row['roles'], list):  
                roles = row['roles']  # Already a list
            else:
                roles = []  # Ensure roles is always a list

            role_objects = Role.objects.filter(name__in=roles)
            with transaction.atomic():
                user.roles.set(role_objects)

            # if not existing_user:
                #  send_mail(
                    #         "Welcome to Our School Platform",
                    #         f"Hello {parent.username},\n\n"
                    #         f"Your account has been created successfully.\n"
                    #         f"Login Email: {parent.email}\n"
                    #         f"Temporary Password: {default_password}\n\n"
                    #         "Please change your password after logging in.",
                    #         settings.DEFAULT_FROM_EMAIL,
                    #         [parent.email],
                    #         fail_silently=True,
                    #     )
            created_users.append(user)

        # Serialize the created users
        serializer = UserSerializer(created_users, many=True)
        response_data = {
            'created_users': serializer.data,
            'skipped_users': skipped_users,
            'message': f'{len(created_users)} user(s) created successfully.'
        }

        return Response(data=response_data, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response(data={'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

# Bulk Student & Parent Registration or Sign Up(Excel File)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser])
def bulk_student_parent_upload(request):
    try:
        if 'file' not in request.FILES:
            print('file not received')
            return Response({'error': 'No file uploaded.'}, status=status.HTTP_400_BAD_REQUEST)

        file = request.FILES['file']
        if not file.name.endswith('.xlsx'):
            return Response({'error': 'File must be an Excel file (.xlsx).'}, status=status.HTTP_400_BAD_REQUEST)

        # Read the Excel file
        df = pd.read_excel(file)
        print(df)

        # Convert all column names to lowercase
        df.columns = df.columns.str.lower()

        required_columns = ['parent_email', 'parent_username', 'parent_phone', 'parent_gender', 'parent_location',
                            'student_email', 'student_username', 'student_phone', 'student_gender', 'student_location',
                            'class_name', 'academic_year', 'school_name', 'campus_name']
        
        if not all(column in df.columns for column in required_columns):
            return Response(
                {'error': f'File must contain the following columns: {required_columns}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        created_users = []
        skipped_users = []
        relationships_created = []

        with transaction.atomic():
            for _, row in df.iterrows():
                parent_email = str(row['parent_email']).strip().lower() if pd.notna(row['parent_email']) else None
                parent_username = str(row['parent_username']).strip() if pd.notna(row['parent_username']) else None
                student_email = str(row['student_email']).strip().lower() if pd.notna(row['student_email']) else None
                student_username = str(row['student_username']).strip() if pd.notna(row['student_username']) else None

                parent_phone = row.get('parent_phone')
                parent_gender = row.get('parent_gender')
                parent_location = row.get('parent_location')

                student_phone = row.get('student_phone')
                student_gender = row.get('student_gender')
                student_location = row.get('student_location')

                school_name = row.get('school_name')
                campus_name = row.get('campus_name')

                class_name = str(row.get('class_name')).strip() if pd.notna(row.get('class_name')) else None
                academic_year = row.get('academic_year')

                # Fetch the class ID using the class name
                if class_name:
                    class_obj = Class.objects.filter(name=class_name).first()
                    if not class_obj:
                        skipped_users.append({
                            "student": {"email": student_email, "username": student_username},
                            "reason": f"Class '{class_name}' does not exist"
                        })
                        continue  # Skip if class not found
                    class_id = class_obj.id
                else:
                    class_id = None

                # Fetch the academic year object
                if academic_year:
                    academic_year_obj = AcademicYear.objects.filter(start_year=academic_year).first()
                    if not academic_year_obj:
                        skipped_users.append({
                            "student": {"email": student_email, "username": student_username},
                            "reason": f"Academic year '{academic_year}' does not exist"
                        })
                        continue  # Skip if academic year not found
                else:
                    academic_year_obj = None

                # Check if users already exist
                existing_parent = User.objects.filter(email=parent_email).first() or User.objects.filter(username=parent_username).first()
                existing_student = User.objects.filter(email=student_email).first() or User.objects.filter(username=student_username).first()

                if existing_parent and existing_student:
                    skipped_users.append({
                        "parent": {"email": parent_email, "username": parent_username},
                        "student": {"email": student_email, "username": student_username},
                        "reason": "Both parent and student already exist"
                    })
                    continue  # Skip this pair

                # Generate a default password for both users
                default_password = get_random_string(8)

                # CREATE PARENT USER (if not exists)
                if not existing_parent:
                    parent = User.objects.create(
                        email=parent_email if parent_email else None,
                        username=parent_username,
                        phone=parent_phone,
                        gender=parent_gender,
                        location=parent_location,
                        passcode=default_password,
                        password=make_password(default_password),
                        school=school_name,
                        campus=campus_name
                    )
                    parent_role, _ = Role.objects.get_or_create(name="Parent")
                    parent.roles.add(parent_role)
                else:
                    parent = existing_parent

                # CREATE STUDENT USER (if not exists)
                if not existing_student:
                    student = User.objects.create(
                        email=student_email if student_email else None,
                        username=student_username,
                        phone=student_phone,
                        gender=student_gender,
                        location=student_location,
                        passcode=default_password,
                        password=make_password(default_password),
                        school=school_name,
                        campus=campus_name
                    )
                    student_role, _ = Role.objects.get_or_create(name="Student")
                    student.roles.add(student_role)
                else:
                    student = existing_student

                # HANDLE CLASS ENROLLMENT (Only for new students)
                if not existing_student and class_id:
                    current_enrollment = ClassEnrollment.objects.filter(student=student, status='existing').first()

                    if current_enrollment:
                        # Move previous class enrollment to history
                        HistoricalClassEnrollment.objects.create(
                            student=student,
                            class_enrolled=current_enrollment.class_id,
                            academic_year=current_enrollment.academic_year,
                        )
                        current_enrollment.status = 'promoted'
                        current_enrollment.save()

                    # Enroll student in the new class
                    ClassEnrollment.objects.create(
                        student=student,
                        class_id=class_obj,
                        academic_year=academic_year_obj,
                        status='existing'
                    )

                # CREATE STUDENT-PARENT RELATIONSHIP
                student_parent_relation, created = StudentParentRelation.objects.get_or_create(
                    student=student, parent=parent
                )

                if created:
                    relationships_created.append(StudentParentRelationSerializer(student_parent_relation).data)

                # SEND EMAILS (if email exists)
                    # if not existing_parent and parent_email:
                    #     send_mail(
                    #         "Welcome to Our School Platform",
                    #         f"Hello {parent.username},\n\n"
                    #         f"Your account has been created successfully.\n"
                    #         f"Login Email: {parent.email}\n"
                    #         f"Temporary Password: {default_password}\n\n"
                    #         "Please change your password after logging in.",
                    #         settings.DEFAULT_FROM_EMAIL,
                    #         [parent.email],
                    #         fail_silently=True,
                    #     )

                    # if not existing_student and student_email:
                    #     send_mail(
                    #         "Welcome to Our School Platform",
                    #         f"Hello {student.username},\n\n"
                    #         f"Your account has been created successfully.\n"
                    #         f"Login Email: {student.email}\n"
                    #         f"Temporary Password: {default_password}\n\n"
                    #         "Please change your password after logging in.",
                    #         settings.DEFAULT_FROM_EMAIL,
                    #         [student.email],
                    #         fail_silently=True,
                    #     )

                # Store created users for response
                created_users.append({
                    "parent": UserSerializer(parent).data,
                    "student": UserSerializer(student).data
                })

        return Response(
            {
                "message": "Bulk registration completed",
                "users_created": created_users,
                "users_skipped": skipped_users,
                "relationships_created": relationships_created,
            },
            status=status.HTTP_201_CREATED,
        )

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



# Endpoint to verify email
@api_view(['GET'])
@permission_classes([])
def verify_email(request, verification_token):
    try:
        user = get_object_or_404(User, email_verification_token=verification_token, email_verified=False)

        # Verify the email and update the user
        user.email_verified = True
        user.email_verification_token = None  # Clear the token
        user.save()

        # Redirect to the verification success page
        return render(request,'email_verification_success.html')
    except:
        return render(request, 'email_verification_error.html')
    

# Login user
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def login(request):
    email = request.data['email']
    password = request.data['password']

    user = User.objects.filter(email=email).first()

    if user is None:
        raise AuthenticationFailed({'message': 'User not found!'})

    if not user.check_password(password):
        raise AuthenticationFailed({'message': 'Incorrect password!'})

    if not user.email_verified:
        return Response({'message': 'Email not verified. Please check your email for a verification link.'}, status=status.HTTP_400_BAD_REQUEST)

    tokens = create_jwt_pair_for_user(user)

    response = {'message': 'Login Successful', 'tokens': tokens}

    return Response(data=response, status=status.HTTP_200_OK)


# Logout User
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def logout(request):
    try:
        refresh_token = request.data['refresh_token']
        if refresh_token:
            token = RefreshToken(refresh_token)
            # print(token)
            token.blacklist()  # Invalidate the token
            print(token.blacklist())
            return Response(data={'message': 'Logout Successful'}, status=status.HTTP_200_OK)
        else:
            return Response(data={'message': 'No refresh token provided'}, status=status.HTTP_400_BAD_REQUEST)
    except TokenError as e:
        return Response(data={'message': f'Token Error: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response(data={'message': 'Logout Failed'}, status=status.HTTP_400_BAD_REQUEST)
    

# Endpoint to request for forgot password reset
@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def request_password_reset(request):
    if request.user.is_authenticated:  # If the user is logged in
        email = request.user.email
    else:  # If the user is not logged in
        email = request.data.get('email')
    
    try:
        user_profile = User.objects.get(email=email)
        print(user_profile)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Generate a random 6-digit code (you can adjust the length)
    password_reset_code = ''.join(random.choice('0123456789') for _ in range(6))

    # Store the code in the user's profile or a separate model
    user_profile.password_reset_code = password_reset_code
    user_profile.save()

    # Send the code to the user's email
    send_mail(
        'Password Reset Code',
        f'Your password reset code is: {password_reset_code}',
        'noreply@example.com',
        [email],
        fail_silently=False,
    )

    return Response({'message': 'Password reset code sent to your email.'}, status=status.HTTP_200_OK)


# Endpoint to verify the code sent to the user's email when entered
@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def verify_reset_code(request):
    code = request.data.get('code')
    if request.user.is_authenticated:  # If the user is logged in
        email = request.user.email
    else:  # If the user is not logged in
        email = request.data.get('email')
    
    try:
        user_profile = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Verify if the provided code matches the stored code
    if user_profile.password_reset_code == code:
        # If the code is valid, delete the code from the user's profile
        user_profile.password_reset_code = None
        user_profile.save()
        
        # Return a success message
        return Response({'message': 'Code is valid and has been deleted.'}, status=status.HTTP_200_OK)
    else:
        return Response({'error': 'Invalid code.'}, status=status.HTTP_400_BAD_REQUEST)


# Endpoint for users to reset their password after successfully verifying the code sent.
@api_view(['POST'])
@authentication_classes([])
@permission_classes([permissions.AllowAny])
def reset_password(request):
    email = request.data.get('email')
    password = request.data.get('password')
    
    try:
        user_profile = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

    # Reset the user's password (you may want to add more validation here)
    user_profile.password = make_password(password)
    user_profile.save()

    return Response({'message': 'Password reset successful.'}, status=status.HTTP_200_OK)


# Endpoint for resetting a user's password in their profile
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def change_password(request):
    serializer = PasswordResetSerializer(data=request.data)

    if serializer.is_valid():
        user = request.user
        current_password = serializer.validated_data['current_password']
        new_password = serializer.validated_data['new_password']

        # Verify the current password
        if check_password(current_password, user.password):
            # Set the new password and update the session authentication hash
            user.set_password(new_password)
            user.save()
            update_session_auth_hash(request, user)

            return Response({'message': 'Password updated successfully.'}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Current password is incorrect.'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PUT'])
@permission_classes([permissions.IsAuthenticated])
def update_profile(request):
    try:
        # Get the authenticated user's profile
        user_profile = User.objects.get(email=request.user.email)
        
        # Combine request data with request.FILES if a file is sent
        data = request.data.copy()
        
        # Check if there's a file in the request
        if 'profile_picture' in request.FILES:
            data['profile_picture'] = request.FILES['profile_picture']

        # Partial update with the serializer
        serializer = UserSerializer(user_profile, data=data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Profile updated successfully', 'data': serializer.data}, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    except ObjectDoesNotExist:
        return Response({'error': 'User profile not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    except Exception as e:
        return Response({'error': 'Server error', 'details': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# Endpoint to retrieve user's profile details
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user(request, user_id):
    try:
        # First, try to get the user from the User model
        try:
            user = User.objects.get(id=user_id)
            profile_data = UserSerializer(user).data

            if user.has_role('Teacher'):
                # Fetch teacher-specific data
                classes = TeacherLevelClass.objects.filter(teacher=user)
                classes_data = TeacherLevelClassSerializer(classes, many=True).data
                return Response({'profile': profile_data, 'classes': classes_data}, status=status.HTTP_200_OK)

            elif user.has_role('Parent'):
                # Fetch parent-specific data
                student_relations = StudentParentRelation.objects.filter(parent=user)
                children = []
                for relation in student_relations:
                    student = relation.student
                    enrollment = student.class_enrollment.filter(status='existing').first()
                    class_data = {
                        'class_id': enrollment.class_id.id if enrollment else None,
                        'class_name': enrollment.class_id.name if enrollment else 'No current class',
                    }
                    children.append({
                        'student_id': student.id,
                        'name': student.name,
                        'current_class': class_data,
                        'age': student.age,
                    })
                profile_data['children'] = children
                return Response({'profile': profile_data}, status=status.HTTP_200_OK)

            return Response({'profile': profile_data}, status=status.HTTP_200_OK)

        except User.DoesNotExist:
            # If the user is not found, try to find a Student with the same ID
            try:
                student = Student.objects.get(id=user_id)
                # Serialize student-specific data
                student_data = {
                    'id': student.id,
                    'name': student.name,
                    'date_of_birth': student.date_of_birth,
                    'age': student.age,
                    'gender': student.gender,
                    'profile_picture': student.student_profile_pic.url if student.student_profile_pic else None,
                }
                return Response({'profile': student_data}, status=status.HTTP_200_OK)

            except Student.DoesNotExist:
                # If neither User nor Student is found
                return Response({'error': 'User or Student not found'}, status=status.HTTP_404_NOT_FOUND)

    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# A search for Student, Teachers, Parents and Headmaster names
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search(request):
    query = request.GET.get('q', '')
    print(f"Query: {query}")  # Debugging line
    if query:
        user_results = User.objects.filter(
            Q(username__icontains=query) |
            Q(email__icontains=query)
        )
        student_results = Student.objects.filter(
            Q(username__icontains=query)
        )

        user_serializer = UserSerializer(user_results, many=True)
        student_serializer = StudentSerializer(student_results, many=True)
        
        results = user_serializer.data + student_serializer.data
    else:
        results = []

    return Response(results)


# Endpoint to validate token from chat system
@api_view(['GET'])
def validate_token(request):
    auth_header = request.headers.get('Authorization', '')
    if not auth_header.startswith('Bearer '):
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)

    token = auth_header.split(' ')[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        User = get_user_model()
        user = User.objects.get(id=payload["user_id"])
        return Response({
            "id": user.id,
            "username": user.username,
            "school_id": user.school,
            "campus_id": user.campus,
        })
    except jwt.ExpiredSignatureError:
        return Response({"error": "Token expired"}, status=status.HTTP_401_UNAUTHORIZED)
    except jwt.InvalidTokenError:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)


class ValidateStudentAPIView(APIView):
    """
    API to validate if a student exists by ID.
    """
    permission_classes = [permissions.AllowAny]
    def get(self, request, student_id):
        try:
            student = User.objects.get(id=student_id)
            return Response({
                'id': student.id,
                'name': student.name,
                'exists': True
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response({'error': 'Student not found', 'exists': False}, status=status.HTTP_404_NOT_FOUND)
        
class RoleCreateView(APIView):
    permission_classes=[permissions.AllowAny]
    def post(self, request):
        """Handle both single and bulk role creation"""
        
        # Check if the request data is a list (bulk creation) or a single object
        if isinstance(request.data, list):
            serializer = RoleSerializer(data=request.data, many=True)
        else:
            serializer = RoleSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)