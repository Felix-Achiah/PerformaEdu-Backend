from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import NotificationPreference
from .serializers import NotificationPreferenceSerializer

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_notification_preference(request):
    user = request.user

    try:
        notification_preference = NotificationPreference.objects.get(user=user, notification_type=request.data.get('notification_type'))
    except NotificationPreference.DoesNotExist:
        notification_preference = NotificationPreference(user=user)

    serializer = NotificationPreferenceSerializer(notification_preference, data=request.data)

    if serializer.is_valid():
        serializer.save()
        message = 'Notification preference updated successfully.' if serializer.data['is_active'] else 'Notification preference deactivated successfully.'
        return Response({'message': message}, status=status.HTTP_200_OK)
    else:
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
