from django.contrib import admin
from .models import Account



class AccountAdmin(admin.ModelAdmin):
    # Username maydonini admin interfeysidan chiqarib tashlash
    exclude = ('username',)

    # Qo'shimcha sozlamalar
    list_display = ('email', 'first_name', 'last_name', 'phone', 'username', 'is_active', 'is_staff')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    readonly_fields = ('date_joined', 'last_login')

    # Foydalanuvchi yaratilgan vaqtni faqat o'qish rejimida qoldirish
    filter_horizontal = ()
    list_filter = ()
    fieldsets = ()

# Adminga modelni ro'yxatdan o'tkazish
admin.site.register(Account, AccountAdmin)
