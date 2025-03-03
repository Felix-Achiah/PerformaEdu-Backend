from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

User = get_user_model()

class CustomRefreshToken(RefreshToken):
    @classmethod
    def for_user(cls, user):
        token = super().for_user(user)
        token['email'] = user.email
        token['username'] = user.username 
        token['roles'] = [role.name for role in user.roles.all()] # Add custom claims to the token payload
        return token

def create_jwt_pair_for_user(user: User):
    refresh = CustomRefreshToken.for_user(user)

    tokens = {
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh)
    }

    return tokens
