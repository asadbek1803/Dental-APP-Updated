from django.urls import path
from .views import login_view, logout_view, settings_view, backup_database, remove_profile_image, toggle_user_ban, edit_user, remove_user_profile_image, delete_user, reset_user_password, upload_backup



urlpatterns = [
    path('login/', login_view, name='login'),  # Foydalanuvchini tizimga kirish sahifasi
    path('logout/', logout_view, name='logout'),  # Foydalanuvchini tizimdan chiqish sahifasi
    path('settings/', settings_view, name='settings'),
    path('settings/backup/', backup_database, name='backup_database'),
    path('settings/remove-profile-image/', remove_profile_image, name='remove_profile_image'),
    path('settings/toggle-ban/', toggle_user_ban, name='toggle_user_ban'),
    path('settings/edit-user/<int:user_id>/', edit_user, name='edit_user'),
    path('settings/remove-profile-image/<int:user_id>/', remove_user_profile_image, name='remove_user_profile_image'),
    path('settings/delete-user/<int:user_id>/', delete_user, name='delete_user'),
    path('settings/reset-password/<int:user_id>/', reset_user_password, name='reset_user_password'),
    path('settings/upload-backup/', upload_backup, name='upload_backup'),
]