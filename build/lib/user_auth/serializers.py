from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'password', 'username', 'phone', 'profile_picture' ,'roles', 'profession', 'location', 'bio', 'created_at']
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        email = validated_data.get('email', None)

        if email:
            # Ensure email is stored in lowercase
            email = email.lower()
            validated_data['email'] = email

        instance = self.Meta.model(**validated_data)

        if password is not None:
            try:
                validate_password(password, instance)
            except ValidationError as e:
                raise serializers.ValidationError({'password': e.messages})
                
            instance.set_password(password)
        instance.save()
        return instance
    
    def update(self, instance, validated_data):
        # Update user fields here
        instance.email = validated_data.get('email', instance.email)
        instance.username = validated_data.get('username', instance.username)
        instance.phone = validated_data.get('phone', instance.phone)
        instance.profile_picture = validated_data.get('profile_picture', instance.profile_picture)
        instance.profession = validated_data.get('profession', instance.profession)
        instance.location = validated_data.get('location', instance.location)
        instance.bio = validated_data.get('bio', instance.bio)

        instance.save()
        return instance


class PasswordResetSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField()
