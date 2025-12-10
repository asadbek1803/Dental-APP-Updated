from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.conf import settings
import os
import shutil
import json
import random
import sqlite3
from django.db import connection
import string
from datetime import datetime
from django.views.decorators.http import require_POST
from .models import Account  # Assuming you have an Account model defined in models.py


# Create your views here.


def login_view(request):
    """
    Foydalanuvchini tizimga kirish sahifasi.
    """
    if request.user.is_authenticated:
        messages.info(request, "Siz allaqachon tizimga kirgansiz!")
        return redirect('home')
    if request.method == 'POST':
        # Foydalanuvchi ma'lumotlarini olish va tizimga kirish
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        # Remove any spaces or special characters from phone number
        phone = ''.join(filter(str.isdigit, phone))
        # Add +998 prefix if not present
        if not phone.startswith('998'):
            phone = '998' + phone
        phone = '+' + phone
        # print(f"Phone: {phone}, Password: {password}")
        # Foydalanuvchini tizimga kirish
        user = authenticate(request, phone=phone, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, "Tizimga muvaffaqiyatli kirdingiz!")
            return redirect('home')  # Tizimga muvaffaqiyatli kirgandan so'ng asosiy sahifaga yo'naltirish
        else:
            message = "Parol yoki Login xato!"
            return render(request=request, template_name='accounts/index.html', context={'error': message})

    return render(request, 'accounts/index.html')  # Kirish sahifasini ko'rsatish


def logout_view(request):
    """
    Foydalanuvchini tizimdan chiqish sahifasi.
    """
    if not request.user.is_authenticated:
        messages.error(request, "Siz tizimga kirgan emassiz!")
        return redirect('login')
    logout(request)  # Foydalanuvchini tizimdan chiqish
    messages.success(request, "Tizimdan muvaffaqiyatli chiqdiz!")
    return redirect('login')  # Tizimdan muvaffaqiyatli chiqqandan so'ng kirish sahifasiga yo'naltirish


@login_required
def settings_view(request):
    if not request.user.is_authenticated:
        messages.error(request, "Siz tizimga kirgan emassiz!")
        return redirect('login')
    # Generate random password for user creation
    random_password = ''.join(random.choice(string.ascii_letters + string.digits) for _ in range(12))
    
    # Profile update
    if request.method == 'POST' and request.POST.get('form_type') == 'profile':
        email = request.POST.get('email', '').strip()
        if email and Account.objects.filter(email=email).exclude(id=request.user.id).exists():
            messages.error(request, 'Bu email allaqachon mavjud!')
            return redirect('settings')

        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = email
        
        # Handle profile image upload
        if 'profile_image' in request.FILES:
            request.user.profile_image = request.FILES['profile_image']
        
        request.user.save()
        messages.success(request, 'Profil ma\'lumotlari muvaffaqiyatli yangilandi!')
        return redirect('settings')
    
    # Password change
    if request.method == 'POST' and request.POST.get('form_type') == 'password':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        if not request.user.check_password(current_password):
            messages.error(request, 'Joriy parol noto\'g\'ri!')
        elif new_password != confirm_password:
            messages.error(request, 'Yangi parol va tasdiqlash mos kelmadi!')
        else:
            request.user.set_password(new_password)
            request.user.save()
            messages.success(request, 'Parol muvaffaqiyatli o\'zgartirildi!')
            return redirect('login')
    
    # Add new user (admin only)
    if request.method == 'POST' and request.POST.get('form_type') == 'add_user' and request.user.is_admin:
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        phone = request.POST.get('phone')
        email = request.POST.get('email', '').strip() or None
        role = request.POST.get('role')
        temp_password = request.POST.get('temp_password')
        
        try:
                
            user = Account.objects.create_user(
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                password=temp_password
            )
            
            # Set role specific permissions
            if role == 'admin':
                user.is_admin = True
                user.is_staff = True
            elif role == 'doctor':
                # Add doctor specific permissions
                pass
            
            user.save()
            messages.success(request, 'Foydalanuvchi muvaffaqiyatli yaratildi!')
        except Exception as e:
            messages.error(request, f'Foydalanuvchi yaratishda xatolik: {str(e)}')
        
        return redirect('settings')
    
    # Security settings
    if request.method == 'POST' and request.POST.get('form_type') == 'security_settings':
        request.user.two_factor_auth = 'two_factor_auth' in request.POST
        request.user.session_timeout = 'session_timeout' in request.POST
        request.user.save()
        messages.success(request, 'Xavfsizlik sozlamalari saqlandi!')
        return redirect('settings')
    
    # Get all users for admin
    users = []
    if request.user.is_admin:
        users = Account.objects.all().order_by('-date_joined')
    
    # Get login history (simplified for this example)
    login_history = []
    
    context = {
        'users': users,
        'login_history': login_history,
        'random_password': random_password,
    }
    return render(request, 'dashboard/settings.html', context)

@login_required
def backup_database(request):
    if not request.user.is_admin and not request.is_authenticated:
        messages.error(request, 'Sizda backup olish uchun ruxsat yo\'q!')
        return redirect('settings')
    
    # Create backup directory if not exists
    backup_dir = os.path.join(settings.MEDIA_ROOT, 'backups')
    os.makedirs(backup_dir, exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'db_backup_{timestamp}.sqlite3'
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Copy the database file
    db_path = settings.DATABASES['default']['NAME']
    shutil.copy2(db_path, backup_path)
    
    # Create response
    response = HttpResponse(open(backup_path, 'rb'), content_type='application/x-sqlite3')
    response['Content-Disposition'] = f'attachment; filename="{backup_filename}"'
    return response

@login_required
def upload_backup(request):
    if not request.user.is_admin and not request.is_authenticated:
        messages.error(request, 'Sizda backup yuklash uchun ruxsat yo\'q!')
        return redirect('settings')
    
    if request.method == 'POST' and 'backup_file' in request.FILES:
        backup_file = request.FILES['backup_file']
        
        # Validate file extension
        if not backup_file.name.endswith('.sqlite3'):
            messages.error(request, 'Faqat .sqlite3 formatidagi fayllarni yuklashingiz mumkin!')
            return redirect('settings')
        
        try:
            # Create temp directory if not exists
            temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Save uploaded file temporarily
            temp_path = os.path.join(temp_dir, 'temp_backup.sqlite3')
            with open(temp_path, 'wb+') as destination:
                for chunk in backup_file.chunks():
                    destination.write(chunk)
            
            # Validate the SQLite database
            try:
                conn = sqlite3.connect(temp_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                if not tables:
                    raise ValueError("Database file is empty or corrupted")
                conn.close()
            except sqlite3.Error as e:
                raise ValueError(f"Noto'g'ri SQLite fayli: {str(e)}")
            
            # Create backup of current database before restoring
            current_db_path = settings.DATABASES['default']['NAME']
            backup_current_path = os.path.join(settings.MEDIA_ROOT, 'backups', f'pre_restore_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.sqlite3')
            shutil.copy2(current_db_path, backup_current_path)
            
            # Close all database connections
            connection.close()
            
            # Replace current database with uploaded one
            shutil.copy2(temp_path, current_db_path)
            
            # Clean up temp file
            os.remove(temp_path)
            
            messages.success(request, 'Backup muvaffaqiyatli yuklandi va bazaga qo\'yildi!')
            return redirect('settings')
            
        except Exception as e:
            messages.error(request, f'Backup yuklashda xatolik: {str(e)}')
            return redirect('settings')
    
    return redirect('settings')



@require_POST
@login_required
def remove_profile_image(request):
    if request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    if request.user.profile_image:
        # Delete the old file if it's not the default
        if request.user.profile_image.name != 'default_profile_image.png':
            request.user.profile_image.delete(save=False)
        request.user.profile_image = 'default_profile_image.png'
        request.user.save()
        return JsonResponse({'success': True})
    return JsonResponse({'success': False})

@require_POST
@login_required
def toggle_user_ban(request):

    # Check if request is AJAX
    if not request.user.is_authenticated:
        redirect('login')
    if request.headers.get('X-Requested-With') != 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'error': 'Faqlat AJAX so\'rovlari qabul qilinadi'
        }, status=400)

    try:
        # Parse JSON data
        data = json.loads(request.body)
        user_id = data.get('user_id')
        action = data.get('action')

        # Validate input
        if not user_id or not action or action not in ['ban', 'unban']:
            return JsonResponse({
                'success': False,
                'error': 'Noto\'g\'ri parametrlar'
            }, status=400)

        # Get user
        user = get_object_or_404(Account, id=user_id)

        # Check permissions and prevent self-ban
        if not request.user.is_admin:
            return JsonResponse({
                'success': False,
                'error': 'Ruxsat etilmagan'
            }, status=403)

        if user == request.user:
            return JsonResponse({
                'success': False,
                'error': 'O\'zingizni bloklab qo\'ya olmaysiz'
            }, status=403)

        # Perform action
        if action == 'ban':
            user.is_banned = True
            user.is_active = False
        else:
            user.is_banned = False
            user.is_active = True

        user.save()

        return JsonResponse({
            'success': True,
            'message': f'Foydalanuvchi muvaffaqiyatli {action} qilindi'
        })

    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Noto\'g\'ri JSON formati'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
   
    



@login_required
def edit_user(request, user_id):
    if not request.user.is_authenticated:
        messages.error(request, "Siz tizimga kirgan emassiz!")
        return redirect('login')
    user_account = get_object_or_404(Account, id=user_id)
    
    if not request.user.is_admin and request.user != user_account:
        messages.error(request, "Sizda bu foydalanuvchini tahrirlash uchun ruxsat yo'q!")
        return redirect('settings')
    
    if request.method == 'POST':
        # Update basic info
        user_account.first_name = request.POST.get('first_name', '')
        user_account.last_name = request.POST.get('last_name', '')
        user_account.email = request.POST.get('email', '')
        
        # Handle profile image upload
        if 'profile_image' in request.FILES:
            user_account.profile_image = request.FILES['profile_image']
        
        # Admin-only fields
        if request.user.is_admin and request.user != user_account:
            role = request.POST.get('role')
            if role == 'admin':
                user_account.is_admin = True
                user_account.is_staff = True
            elif role == 'staff':
                user_account.is_admin = False
                user_account.is_staff = True
            else:
                user_account.is_admin = False
                user_account.is_staff = False
            
            user_account.is_active = 'is_active' in request.POST
            user_account.is_banned = 'is_banned' in request.POST
        
        user_account.save()
        messages.success(request, 'Foydalanuvchi ma\'lumotlari muvaffaqiyatli yangilandi!')
        return redirect('settings')
    
    # Get activity logs (you'll need to implement this)
    activity_logs = []
    
    context = {
        'user_account': user_account,
        'activity_logs': activity_logs,
    }
    return render(request, 'dashboard/edit_user.html', context)

@require_POST
@login_required
def remove_user_profile_image(request, user_id):
    if not request.user.is_authenticated:
        redirect('login')
    if not request.user.is_admin:
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    try:
        user = Account.objects.get(id=user_id)
        if user.profile_image:
            # Delete the old file if it's not the default
            if user.profile_image.name != 'default_profile_image.png':
                user.profile_image.delete(save=False)
            user.profile_image = 'default_profile_image.png'
            user.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'error': 'No profile image'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
def delete_user(request, user_id):
    if not request.user.is_authenticated:
        redirect('login')
    try:
        user = Account.objects.get(id=user_id)
        if user == request.user:
            return JsonResponse({'success': False, 'error': 'You cannot delete yourself'})
        user.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@require_POST
@login_required
def reset_user_password(request, user_id):
    if not request.user.is_authenticated:
        redirect('login')
    if not request.user.is_admin:
        return JsonResponse({'success': False, 'error': 'Permission denied'})
    
    try:
        user = Account.objects.get(id=user_id)
        new_password = request.POST.get('new_password')
        if not new_password:
            return JsonResponse({'success': False, 'error': 'New password required'})
        
        user.set_password(new_password)
        user.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})