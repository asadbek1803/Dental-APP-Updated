from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import RegexValidator
import random


class MyAccountManager(BaseUserManager):
    def create_user(self, first_name, last_name, phone, email=None, password=None):
        

        username = self._generate_unique_username()

        user = self.model(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=self.normalize_email(email),
            phone=phone,
        )

        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_superuser(self, first_name, last_name,  phone, password=None, email=None):
        user = self.create_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            password=password
        )

        user.is_active = True
        user.is_admin = True
        user.is_staff = True
        user.is_superuser = True

        user.save(using=self._db)

        return user

    def _generate_unique_username(self):
        while True:
            username = f"#user{random.randint(1000000, 9999999)}"
            if not Account.objects.filter(username=username).exists():
                return username



class Account(AbstractBaseUser, PermissionsMixin):  # <--- PermissionsMixin qo'shildi
    class Meta:
        permissions = [('can_view_account', 'Can view account')]
        default_permissions = []

    first_name = models.CharField(max_length=50, blank=True, null=True)
    last_name = models.CharField(max_length=50, blank=True, null=True)
    profile_image = models.ImageField(upload_to='profile_images/', default="default_profile_image.png", blank=True, null=True)
    
    username = models.CharField(max_length=50, unique=True, editable=False)
    phone = models.CharField(max_length=15, unique=True, validators=[RegexValidator(regex=r'^\+998\d{9}$', message='Phone number must start with +998 followed by 9 digits')])
    email = models.EmailField(max_length=100, unique=True, blank=True, null=True)
    

    # required fields
    date_joined = models.DateTimeField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_superadmin = models.BooleanField(default=False)
    is_banned = models.BooleanField(default=False, blank=True, null=True)

    USERNAME_FIELD = 'phone'
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = MyAccountManager()

    def __str__(self):
        return self.username

    def has_perm(self, perm, obj=None):
        return self.is_admin

    def has_module_perms(self, app_label):
        return True

    def profile_image_exists(self):
        return bool(self.profile_image)




