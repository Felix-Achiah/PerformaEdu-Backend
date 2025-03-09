from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomRefreshToken(RefreshToken):
    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        
        # Add user details to the token payload
        token['email'] = user.email
        token['username'] = user.username or ''
        token['roles'] = [role.name for role in user.roles.all()]
        
        # Add school and campus details
        token['school_id'] = user.school_id if user.school else None
        token['campus_id'] = user.campus_id if user.campus else None
        token['school_name'] = user.school.name if user.school else None
        token['campus_name'] = user.campus.name if user.campus else None

        return token

def create_jwt_pair_for_user(user: User):
    refresh = CustomRefreshToken.for_user(user)

    tokens = {
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh)
    }

    return tokens
