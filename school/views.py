# core/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions
import logging

from .models import School, Campus
from .serializers import SchoolSerializer, CampusSerializer

logger = logging.getLogger(__name__)

class SchoolSignupView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Extract individual fields from request.data
        school_data = {
            'name': request.data.get('name'),
            'logo': request.FILES.get('logo'),
            'country': request.data.get('country'),
            'address': request.data.get('address'),
            'city': request.data.get('city'),
            'postal_code': request.data.get('postal_code'),
            'num_campuses': request.data.get('num_campuses')
        }

        # Validate and save school
        school_serializer = SchoolSerializer(data=school_data)
        if school_serializer.is_valid():
            school = school_serializer.save()
            logger.info(f"School '{school.name}' registered with subdomain '{school.subdomain}'")
        else:
            return Response(school_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # Process campuses (they are still in nested JSON, so extract manually)
        created_campuses = []
        errors = []
        for i in range(int(request.data.get('num_campuses', 0))):
            campus_data = {
                'name': request.data.get(f'campuses[{i}][name]'),
                'city': request.data.get(f'campuses[{i}][city]'),
                'address': request.data.get(f'campuses[{i}][address]'),
                'school': school.id  # Link to school
            }
            campus_serializer = CampusSerializer(data=campus_data)
            if campus_serializer.is_valid():
                campus = campus_serializer.save(school=school)
                created_campuses.append(campus_serializer.data)
            else:
                errors.append(campus_serializer.errors)

        response_data = {
            'school': school_serializer.data,
            'campuses': created_campuses,
            'errors': errors if errors else None
        }
        status_code = status.HTTP_201_CREATED if not errors else status.HTTP_207_MULTI_STATUS
        return Response(response_data, status=status_code)

    

class SchoolListView(APIView):
    """
    GET request to fetch all school details, including their campuses.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """
        Retrieve all schools with their associated campuses.
        """
        try:
            schools = School.objects.all().prefetch_related('campuses')  # Optimize query
            country = request.query_params.get('country')
            if country:
                schools = schools.filter(country=country)
            serializer = SchoolSerializer(schools, many=True)
            logger.info(f"Fetched {len(schools)} schools for user {request.user.username}")
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error fetching schools: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)