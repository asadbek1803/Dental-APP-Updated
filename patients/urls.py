from django.urls import path
from .views import PatientListView, AssessmentView, AddPatientView, PatientUpdateView,PatientDetailView, PatientDeleteView, AssessmentDetailView, AssessmentUpdateView, AssessmentDeleteView, print_patient_card, PatientExportExcelView, PatientExportPDFView

urlpatterns = [
    path('', PatientListView.as_view(), name='patients'),  # Bemorlar ro'yxatini ko'rsatish
    path('assessment/', AssessmentView.as_view(), name='assessment'), 
      # Bemor baholash sahifasi,
    path('assessment/<int:pk>/', AssessmentDetailView.as_view(), name='assessment_detail'),
    path('assessment/<int:pk>/edit/', AssessmentUpdateView.as_view(), name='assessment_edit'),
    path('assessment/<int:pk>/delete/', AssessmentDeleteView.as_view(), name='assessment_delete'),

    path('add/', AddPatientView.as_view(), name='add_patient'),  # Yangi bemor qo'shish sahifasi
    path('update/<int:patient_id>/', PatientUpdateView.as_view(), name='patient_update'),  # Bemor ma'lumotlarini yangilash sahifasi
    path('delete/<int:patient_id>/', PatientDeleteView.as_view(), name='patient_delete'),  # Bemorni o'chirish sahifasi
    path('<int:patient_id>/', PatientDetailView.as_view(), name='patient_detail'),  # Bemorning batafsil ma'lumotlarini ko'rsatish
    path('<int:patient_id>/print-card/', print_patient_card, name='print_patient_card'),
    path('export/excel/', PatientExportExcelView.as_view(), name='export_patients_excel'),  # Bemorlarni Excel formatida eksport qilish
    path('export/pdf/', PatientExportPDFView.as_view(), name='export_patients_pdf'),  # Bemorlarni PDF formatida eksport qilish
]