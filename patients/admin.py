from django.contrib.admin import ModelAdmin
from django.contrib import admin
from .models import Patient, MedicalAssessment, MedicalRecord

# Register your models here.
@admin.register(Patient)
class PatientAdmin(ModelAdmin):
    """
    Bemor modelini admin panelda boshqarish uchun admin klassi.
    """
    list_display = ('full_name', 'date_of_birth', 'age', 'status', 'phone_number', 'visit_date', 'last_coming')
    search_fields = ('full_name', 'phone_number')
    list_filter = ('status', )
    ordering = ('-visit_date',)
    fieldsets = (
        (None, {
            'fields': ('full_name', 'date_of_birth')
            }),
        ('Contact Information', {
            'fields': ('phone_number',)
            }),
        ('Medical Information', {
            'fields': ('status',)
            }),
    )

@admin.register(MedicalAssessment)
class MedicalAssessmentAdmin(ModelAdmin):
    """
    Bemorning tibbiy baholashlarini admin panelda boshqarish uchun admin klassi.
    """
    list_display = ('patient', 'assessment_date')
    search_fields = ('patient__full_name',)
    list_filter = ('assessment_date',)
    ordering = ('-assessment_date',)
    fieldsets = (
        (None, {
            'fields': ('patient', 'assessment_date')
            }),
        ('Assessment Details', {
            'fields': ('description',)
            }),
    )

@admin.register(MedicalRecord)
class MedicalRecordAdmin(ModelAdmin):
    """
    Bemorning tibbiy yozuvlarini admin panelda boshqarish uchun admin klassi.
    """
    list_display = ('patient', 'record_date', 'description')
    search_fields = ('patient__full_name', 'description')
    list_filter = ('record_date',)
    ordering = ('-record_date',)
    fieldsets = (
        (None, {
            'fields': ('patient', 'record_date')
            }),
        ('Record Details', {
            'fields': ('description',)
            }),
    )