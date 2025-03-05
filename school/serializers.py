# core/serializers.py
from rest_framework import serializers
from .models import School, Campus

class CampusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campus
        fields = ['id', 'name', 'city', 'address', 'created_at', 'updated_at']

class SchoolSerializer(serializers.ModelSerializer):
    campuses = CampusSerializer(many=True, read_only=True)
    class Meta:
        model = School
        fields = [
            'id', 'name', 'subdomain', 'logo', 'country', 'address', 'city', 
            'postal_code', 'num_campuses', 'campuses', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'subdomain': {'required': False, 'allow_null': True},
            'logo': {'required': False, 'allow_null': True}
        }

    def validate_subdomain(self, value):
        if value and School.objects.filter(subdomain=value).exists():
            raise serializers.ValidationError("Subdomain already in use.")
        return value