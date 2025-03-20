
from user_auth.models import User, Role

# Create roles if they don't exist
teacher_role, _ = Role.objects.get_or_create(name='Teacher')
admin_role, _ = Role.objects.get_or_create(name='Admin')
headmaster_role, _ = Role.objects.get_or_create(name='Headmaster')
parent_role, _ = Role.objects.get_or_create(name='Parent')
student_role, _ = Role.objects.get_or_create(name='Student')

# Assign roles to a user
# user = User.objects.get(email='"nanaama@email.com"')
# user.roles.add(teacher_role)
