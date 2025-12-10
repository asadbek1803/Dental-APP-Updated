from django.contrib import admin
from django.contrib.admin import ModelAdmin
from .models import Payment
# Register your models here.

@admin.register(Payment)
class PaymentAdmin(ModelAdmin):
    """
    To'lov modelini admin panelda boshqarish uchun admin klassi.
    """
    list_display = ('get_patient_full_name', 'paid_amount', 'payment_date')
    search_fields = ('patient__full_name', 'paid_amount')
    list_filter = ('payment_method', 'payment_date')
    ordering = ('-payment_date',)
    fieldsets = (
        (None, {
            'fields': ('patient', 'paid_amount', 'payment_method')
        }),
    )

    def get_patient_full_name(self, obj):
        return obj.patient.full_name
    get_patient_full_name.short_description = 'Patient Name'