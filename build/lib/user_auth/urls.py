from django.urls import path
from . import views

from rest_framework_simplejwt.views import (
    TokenRefreshView
)



urlpatterns = [
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    path('sign-up/', views.sign_up, name='sign_up'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    # path('personal-details/', views.personal_details, name='personal_details'),

    path('get-user/<int:user_id>/', views.get_user, name='get_user'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('change-password/', views.change_password, name='change_password'),

    # Forgot Password reset endpoints
    path('request-password-reset/', views.request_password_reset, name='request_password_reset'),
    path('verify-reset-code/', views.verify_reset_code, name='verify_reset_code'),
    path('reset-password/', views.reset_password, name='reset_password'),

    # Email Verification token endpoint
    path('verify-email/<str:verification_token>/', views.verify_email, name='verify_email'),
    # path('verify-email/success/', views.verify_email_success, name='verify_email_success'), 

    # Search endpoint
    path('search/', views.search, name='search'),

    # Validate token from chat system endpoint
    path('validate-token/', views.validate_token, name='validate_token'),
]