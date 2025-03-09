from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import User, Role
from student_performance.models import ClassEnrollment
from school.models import School, Campus
from school.serializers import SchoolSerializer, CampusSerializer

class RoleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Role
        fields = ['id', 'name']


class UserSerializer(serializers.ModelSerializer):
    roles = RoleSerializer(many=True, read_only=True)
    class_name = serializers.SerializerMethodField()
    school = SchoolSerializer(read_only=True)  # Serialize school
    campus = CampusSerializer(read_only=True)  # Serialize campus

    class Meta:
        model = User
        fields = [
            'id', 'email', 'password', 'username', 'phone', 'profile_picture', 
            'roles', 'profession', 'location', 'bio', 'created_at', 'is_active', 
            'class_name', 'school', 'campus'
        ]
        extra_kwargs = {
            'password': {'write_only': True},
        }

    def get_class_name(self, obj):
        """
        Fetch the class name where the student has enrollment status 'existing'.
        """
        enrollment = ClassEnrollment.objects.filter(
            student=obj, status="existing"
        ).select_related('class_id').first()

        return enrollment.class_id.name if enrollment and enrollment.class_id else None

    def get_school(self, obj):
        """
        Get the first associated school from the user's roles.
        """
        role = obj.roles.select_related('school').first()
        return SchoolSerializer(role.school).data if role and role.school else None

    def get_campus(self, obj):
        """
        Get the first associated campus from the user's roles.
        """
        role = obj.roles.select_related('campus').first()
        return CampusSerializer(role.campus).data if role and role.campus else None

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        email = validated_data.get('email', None)
        if not email:
            raise serializers.ValidationError({'email': 'This field is required.'})
        validated_data['email'] = email.lower()

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
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = self.context['request'].user
        if not user.check_password(data['current_password']):
            raise serializers.ValidationError({'current_password': 'Incorrect password.'})
        try:
            validate_password(data['new_password'], user)
        except ValidationError as e:
            raise serializers.ValidationError({'new_password': e.messages})
        return data
