import datetime
import logging
import random
import jwt
from django.urls import reverse
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
from rest_framework.decorators import api_view, permission_classes, authentication_classes, renderer_classes
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed
from rest_framework import status, permissions
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from smtplib import SMTPException
from django.db.models import Q

from .models import User
from .serializers import UserSerializer, PasswordResetSerializer
from student_performance.serializers import TeacherLevelClassSerializer, StudentSerializer
from student_performance.models import TeacherLevelClass, Student, StudentParentRelation
from .tokens import create_jwt_pair_for_user
from .utils import generate_verification_token

logger = logging.getLogger(__name__)

# Register new user
@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def sign_up(request):
    try:
        data=request.data
        print(data)
        email = data.get('email')

        existing_user = User.objects.filter(email=data['email']).first()

        # check if user already exists
        if existing_user:
            return Response(data={'error': 'User with this email already exists.'}, status=status.HTTP_400_BAD_REQUEST)

        # Generate a verification token
        verification_token = generate_verification_token()


        user = User.objects.create(
            email = email,
            password = make_password(data.get('password')),
            phone = data.get('phone'),
            username = data.get('username'),
            user_type = data.get('user_type'),
            email_verification_token = verification_token,
        )


        # Send email verification link
        subject = 'Email Verification'
        current_site = get_current_site(request)
        uid = urlsafe_base64_encode(force_bytes(User.objects.get(email=email).pk))
        print(uid)

        verification_url = reverse('verify_email', kwargs={'verification_token': verification_token})
        verification_url = f'http://{current_site}{verification_url}'

        # Create the plain text message
        text_message = f"Click the following link to verify your email: {verification_url}"

        # Create the HTML message
        html_message = render_to_string('email_verification.html', {
            'user': user,
            'verification_url': verification_url,
        })

        from_email = 'felixekow08@gmail.com'  # Replace with your email
        recipient_list = [email]

        # Send the email with both plain text and HTML content
        msg = EmailMultiAlternatives(subject, text_message, from_email, recipient_list)
        msg.attach_alternative(html_message, "text/html")  # Set the content type to HTML

        try:
            msg.send(fail_silently=False)
            response = {'message': 'User Created Successfully. Check your email for verification', 'data': UserSerializer(user).data}

            return Response(data=response, status=status.HTTP_201_CREATED)
        
        except SMTPException as smtp_error:
            # Handle SMTPException
            logger.error(f"Email sending error: {smtp_error}")
            error_message = f"Email sending error: {str(smtp_error)}"
            return Response(data={"error": error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        logger.error(f'An error occurred: {e}')
        error_message = f"An error occurred: {str(e)}"
        return Response(data={"error": error_message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    

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
    print(request.data)

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
        print(f'Received refresh_token: {refresh_token}')
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
# Endpoint to retrieve user's profile details
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_user(request, user_id):
    try:
        # Query the user by ID
        user = User.objects.get(id=user_id)

        # Serialize the user profile data
        profile_data = UserSerializer(user).data

        # Check user type and fetch additional data if the user is a teacher
        if user.has_role('Teacher'):
            classes = TeacherLevelClass.objects.filter(teacher=user)
            classes_data = TeacherLevelClassSerializer(classes, many=True).data
            return Response({'profile': profile_data, 'classes': classes_data}, status=status.HTTP_200_OK)

        # Check if the user is a parent
        elif user.has_role('Parent'):
            # Fetch the parent's chosen students
            student_relations = StudentParentRelation.objects.filter(parent=user)
            children = []
            for relation in student_relations:
                student = relation.student
                # Get the current class information using ClassEnrollment
                enrollment = student.class_enrollment.filter(status='existing').first()
                if enrollment:
                    class_data = {
                        'class_id': enrollment.class_id.id,
                        'class_name': enrollment.class_id.name
                    }
                else:
                    class_data = {
                        'class_id': None,
                        'class_name': 'No current class'
                    }

                # Add student info including current class and age
                children.append({
                    'student_id': student.id,
                    'name': student.name,
                    'current_class': class_data,
                    'age': student.age
                })

            # Add children data to the profile data
            profile_data['children'] = children

            return Response({'profile': profile_data}, status=status.HTTP_200_OK)

        else:
            return Response({'profile': profile_data}, status=status.HTTP_200_OK)

    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

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
            Q(name__icontains=query)
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
            "username": user.username
        })
    except jwt.ExpiredSignatureError:
        return Response({"error": "Token expired"}, status=status.HTTP_401_UNAUTHORIZED)
    except jwt.InvalidTokenError:
        return Response({"error": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)
