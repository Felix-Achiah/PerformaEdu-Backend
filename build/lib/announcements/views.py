from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, permissions

from .models import Announcement
from .serializers import AnnouncementSerializer
from user_auth.permissions import IsAdmin


class AnnouncementAPIView(APIView):
    """
    CRUD operations for Announcements.
    Only admins can create, update, or delete announcements.
    All authenticated users can fetch announcements.
    """

    def get_permissions(self):
        """
        Assign permissions dynamically based on the HTTP method.
        - GET: Any authenticated user.
        - POST, PUT, DELETE: Admin only.
        """
        if self.request.method in ["POST", "PUT", "DELETE"]:
            return [permissions.IsAuthenticated(), IsAdmin()]
        return [permissions.IsAuthenticated()]

    def get(self, request, announcement_id=None):
        """
        Retrieve one or all announcements.
        If `announcement_id` is provided, fetch a single announcement.
        Otherwise, fetch all announcements.
        """
        if announcement_id:
            try:
                announcement = Announcement.objects.get(id=announcement_id)
                serializer = AnnouncementSerializer(announcement)
                return Response(serializer.data, status=status.HTTP_200_OK)
            except Announcement.DoesNotExist:
                return Response({'error': 'Announcement not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            announcements = Announcement.objects.all().order_by('-created_at')
            serializer = AnnouncementSerializer(announcements, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """
        Create one or more announcements dynamically.
        Admin only.
        """
        data = request.data

        if isinstance(data, dict):  # Single announcement
            serializer = AnnouncementSerializer(data=data)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        elif isinstance(data, list):  # Multiple announcements
            serializer = AnnouncementSerializer(data=data, many=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {"error": "Invalid data format. Expected a dictionary or a list."},
            status=status.HTTP_400_BAD_REQUEST
        )

    def put(self, request, announcement_id):
        """
        Update an existing announcement.
        Admin only.
        """
        try:
            announcement = Announcement.objects.get(id=announcement_id)
            serializer = AnnouncementSerializer(announcement, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        except Announcement.DoesNotExist:
            return Response({'error': 'Announcement not found'}, status=status.HTTP_404_NOT_FOUND)

    def delete(self, request, announcement_id):
        """
        Delete an existing announcement.
        Admin only.
        """
        try:
            announcement = Announcement.objects.get(id=announcement_id)
            announcement.delete()
            return Response({'message': 'Announcement deleted successfully'}, status=status.HTTP_204_NO_CONTENT)
        except Announcement.DoesNotExist:
            return Response({'error': 'Announcement not found'}, status=status.HTTP_404_NOT_FOUND)
