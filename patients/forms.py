from django import forms
from .models import MedicalAssessment
from django_select2.forms import Select2Widget

class MedicalAssessmentForm(forms.ModelForm):
    class Meta:
        model = MedicalAssessment
        fields = '__all__'
        widgets = {
            'assessment_date': forms.DateInput(attrs={'type': 'date'}),
            'patient': Select2Widget(attrs={
                'data-placeholder': 'Bemorni qidirish...',
                'data-language': 'uz',
                'data-minimum-input-length': 2,
            }),

            'patient_condition': forms.Select(attrs={
                'class': 'form-select',
                'data-placeholder': 'Bemor holatini tanlang',
            }),
            'assessment': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'treatment_plan': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
            'mhshb_checkup': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'diagnosis': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'additional_notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }