from django.db import models
from django.contrib.auth.models import AbstractUser


class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    id = models.AutoField(primary_key=True)
    email = models.EmailField(unique=True, null=True, blank=True)
    password = models.CharField(max_length=255)
    passcode = models.CharField(max_length=255, null=True, blank=True)
    username = models.CharField(max_length=255, null=True, default='Jim Berk')
    phone = models.CharField(null=True, max_length=255, blank=True)
    profile_picture = models.ImageField(upload_to='profile-picture/', null=True, blank=True)
    cover_picture = models.ImageField(upload_to='cover-picture/', null=True, blank=True)
    roles = models.ManyToManyField(Role, related_name='users')
    gender = models.CharField(max_length=50, null=True)
    profession = models.CharField(max_length=250, null=True, blank=True)
    location = models.CharField(max_length=250, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    bio = models.TextField(max_length=400, null=True, blank=True)
    created_at = models.DateField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateField(auto_now=True)
    
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.CharField(max_length=100, blank=True, null=True)
    password_reset_code = models.CharField(max_length=6, null=True, blank=True)
    is_active = models.BooleanField(default=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['password']

    def __str__(self):
        return self.id

    def has_role(self, role_name):
        return self.roles.filter(name=role_name).exists()