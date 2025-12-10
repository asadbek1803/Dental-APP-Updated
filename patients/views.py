from django.db.models import DecimalField
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View
from .models import Patient, MedicalAssessment, MedicalRecord
from django.shortcuts import get_object_or_404
from django.contrib import messages
from datetime import date
from django.shortcuts import redirect
from django.core.paginator import Paginator
from django.utils import timezone
from django.db.models import Count, Q, Sum
from payments.models import Payment
from .forms import MedicalAssessmentForm
from django.db.models.functions import Coalesce
from decimal import Decimal
import os
from django.conf import settings
from django.template.loader import render_to_string
from xhtml2pdf import pisa
from django.http import HttpResponse
from datetime import datetime

# Add these imports for PDF export functionality
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors




# Create your views here.
class PatientListView(View):
    """
    Optimallashtirilgan bemorlar ro'yxati ko'rinishi
    """
    DEFAULT_ITEMS_PER_PAGE = 25
    DEFAULT_SORT = '-visit_date'
    
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        """
        Asosiy GET so'rovi uchun metod
        """
        # Asosiy querysetni olish
        queryset = self.get_base_queryset()
        
        # Filtrlarni qo'llash
        queryset = self.apply_filters(request, queryset)
        
        # Saralashni qo'llash
        queryset = self.apply_sorting(request, queryset)
        
        # Statistik ma'lumotlar
        stats = self.get_statistics(queryset)
        
        # Paginatsiya
        page_obj = self.paginate_queryset(request, queryset)
        
        context = {
            'patients': page_obj,
            **stats
        }
        
        return render(request, 'dashboard/patients.html', context)
    
    def get_base_queryset(self):
        """
        Asosiy querysetni qaytaradi, annotatsiyalar bilan
        """
        return Patient.objects.annotate(
            payment_count=Count('payments'),
            total_debt=Coalesce(
                Sum('payments__debt'),
                Decimal(0),
                output_field=DecimalField()
            )
        )
    
    def apply_filters(self, request, queryset):
        """
        Barcha filtrlarni qo'llaydi
        """
        # Matnli qidiruv
        queryset = self.apply_search_filter(request, queryset)
        
        # Jins bo'yicha filter
        queryset = self.apply_gender_filter(request, queryset)
        
        # Yosh guruhi bo'yicha filter
        queryset = self.apply_age_group_filter(request, queryset)
        
        # Sana bo'yicha filter
        queryset = self.apply_date_filter(request, queryset)
        
        # Qarz bo'yicha filter
        queryset = self.apply_debt_filter(request, queryset)
        
        return queryset
    
    def apply_search_filter(self, request, queryset):
        search_query = request.GET.get('search', '').strip()
        if search_query:
            return queryset.filter(
                Q(full_name__icontains=search_query) |
                Q(phone_number__icontains=search_query) |
                Q(id__icontains=search_query)
            )
        return queryset
    
    def apply_gender_filter(self, request, queryset):
        gender = request.GET.get('gender', '')
        if gender in ['male', 'female', 'other']:
            if gender == "male":
                return queryset.filter(gender="M")
            elif gender == "female":
                return queryset.filter(gender="F")
            else:
                return queryset.filter(gender="O")
        return queryset
    
    def apply_age_group_filter(self, request, queryset):
        age_group = request.GET.get('age_group', '')
        today = timezone.now().date()
        
        age_filters = {
            'child': Q(date_of_birth__gte=today - timezone.timedelta(days=17*365)),
            'youth': Q(
                date_of_birth__lt=today - timezone.timedelta(days=17*365),
                date_of_birth__gte=today - timezone.timedelta(days=35*365)
            ),
            'adult': Q(
                date_of_birth__lt=today - timezone.timedelta(days=35*365),
                date_of_birth__gte=today - timezone.timedelta(days=60*365)
            ),
            'elderly': Q(date_of_birth__lt=today - timezone.timedelta(days=60*365))
        }
        
        if age_group in age_filters:
            return queryset.filter(age_filters[age_group])
        return queryset
    
    def apply_date_filter(self, request, queryset):
        date_filter = request.GET.get('date_filter', '')
        today = timezone.now().date()
        
        date_filters = {
            'today': Q(visit_date__date=today),
            'week': Q(visit_date__date__gte=today - timezone.timedelta(days=7)),
            'month': Q(visit_date__date__gte=today - timezone.timedelta(days=30))
        }
        
        if date_filter in date_filters:
            return queryset.filter(date_filters[date_filter])
        return queryset
    
    def apply_debt_filter(self, request, queryset):
        debt_filter = request.GET.get('debt', '')
        
        if debt_filter == 'has_debt':
            # Qarzdor bemorlar (umumiy qarzi 0 dan katta)
            return queryset.filter(payments__debt__gt=0).distinct()
        elif debt_filter == 'no_debt':
            # Qarzi yo'q bemorlar (hech qanday qarzi yo'q yoki to'lovlar mavjud emas)
            return queryset.exclude(payments__debt__gt=0).distinct()
        
        return queryset
    
    def apply_sorting(self, request, queryset):
        sort_options = {
            'name-asc': 'full_name',
            'name-desc': '-full_name',
            'date-desc': '-visit_date',
            'date-asc': 'visit_date',
            'age-asc': 'date_of_birth',  # Changed from birth_date to date_of_birth
            'age-desc': '-date_of_birth'  # Changed from birth_date to date_of_birth
        }
        
        sort_by = request.GET.get('sort', 'date-desc')
        return queryset.order_by(sort_options.get(sort_by, self.DEFAULT_SORT))
    
    def get_statistics(self, queryset):
        today = timezone.now().date()
        
        return {
            'patients_count': queryset.count(),
            'today_count': queryset.filter(last_coming=today).count(),
            'pending_count': queryset.filter(status='pending').count(),
            'completed_count': queryset.filter(status='completed').count(),
        }
    
    def paginate_queryset(self, request, queryset):
        page_number = request.GET.get('page', 1)
        items_per_page = int(request.GET.get('items', self.DEFAULT_ITEMS_PER_PAGE))
        paginator = Paginator(queryset, items_per_page)
        return paginator.get_page(page_number)


class PatientDetailView(View):
    """
    Bemorning batafsil ma'lumotlarini ko'rsatish.
    """
    def get(self, request, patient_id):
        if not request.user.is_authenticated:
            return redirect('login')
        """
        Bemorning batafsil ma'lumotlarini olish va ko'rsatish.
        """
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Tibbiy baholashlar (eng yangisi birinchi)
        medical_assessments = MedicalAssessment.objects.filter(
            patient=patient
        ).order_by('-assessment_date')
        
        # Tibbiy yozuvlar (eng yangisi birinchi)
        medical_records = MedicalRecord.objects.filter(
            patient=patient
        ).order_by('-record_date')
        
        # Rentgen rasmlari (faqat rasm borlari)
        rengen_images = MedicalAssessment.objects.filter(
            patient=patient
        ).exclude(
            rengen_image__isnull=True
        ).exclude(
            rengen_image__exact=''
        )
        
        # Jami MHSHB hisoblash
        total_mhshb = medical_assessments.aggregate(
            total=Sum('total_mhshb')
        )['total'] or 0
        
        # To'lovlar bo'yicha ma'lumotlar
        payments = Payment.objects.filter(patient=patient).order_by('-payment_date')
        last_payment = payments.first()
        
        # Jami to'langan summa
        total_paid = payments.aggregate(
            total=Sum('paid_amount')
        )['total'] or 0
        
        # Jami qarz (barcha to'lovlardagi qarzlar yig'indisi)
        total_debt = payments.aggregate(
            total=Sum('debt')
        )['total'] or 0
        
        # Agar to'lovlar bo'yicha qarz 0 bo'lsa, lekin MHSHB to'lanmagan bo'lsa
        if total_debt == 0 and total_mhshb > total_paid:
            total_debt = total_mhshb - total_paid
        
        context = {
            'patient': patient,
            'medical_assessments': medical_assessments,
            'medical_records': medical_records,
            'rengen_images': rengen_images,
            'last_payment': last_payment,
            'total_paid': total_paid,
            'debt': total_debt,
            'total_mhshb': total_mhshb,
            'payments': payments,
        }
        
        return render(request, 'dashboard/patient_detail.html', context)
    
    def post(self, request, patient_id):
        if not request.user.is_authenticated:
            return redirect('login')
        """
        Bemor ma'lumotlarini yangilash POST so'rovi.
        """
        
        patient = get_object_or_404(Patient, id=patient_id)
        if request.method == 'POST':
            amount = request.POST.get('amount', '0')
            paid = request.POST.get('paid_amount', '0')
            payment_date = request.POST.get('payment_date', timezone.now().date())
            notes = request.POST.get('notes', '')
            payments_method = request.POST.get('payments_method', 'cash')
            pay = Payment(
                patient=patient,
                total_amount=float(amount),
                paid_amount=float(paid),
                debt=float(amount) - float(paid),
                payment_date=timezone.datetime.strptime(payment_date, '%Y-%m-%d').date(),
                payment_method=payments_method
            ).save()
            messages.success(request, 'To\'lov muvaffaqiyatli qo\'shildi!')
            return redirect('patient_detail', patient_id=patient.id)


   

class AssessmentView(View):
    """
    Bemor baholash sahifasi.
    """
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        """

        Bemor baholash sahifasini ko'rsatish.
        """
        assessments = MedicalAssessment.objects.select_related('patient').all().order_by('-assessment_date')
        
        # Filtering logic
        patient_name = request.GET.get('patient_name', '')
        condition = request.GET.get('condition', '')
        assessment_date = request.GET.get('assessment_date', '')
        assessment_form = MedicalAssessmentForm()
        if patient_name:
            assessments = assessments.filter(patient__full_name__icontains=patient_name)
        if condition:
            assessments = assessments.filter(patient_condition=condition)
        if assessment_date:
            assessments = assessments.filter(assessment_date=assessment_date)
        
        context = {
            'assessments': assessments,
            'total_assessments': MedicalAssessment.objects.count(),
            'today_assessments': MedicalAssessment.objects.filter(assessment_date=date.today()).count(),
            'form': assessment_form,
            'emergency_cases': MedicalAssessment.objects.filter(patient_condition__in=['extraction', 'pulpitis']).count(),
            'xray_cases': MedicalAssessment.objects.filter(patient_condition='xray').count(),
        }
        return render(request, 'dashboard/assessment.html', context)

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        """
        Yangi tibbiy baholash qo'shish.
        """
        form = MedicalAssessmentForm(request.POST, request.FILES)
        if form.is_valid():
            assessment = form.save()
            messages.success(request, 'Tibbiy baholash muvaffaqiyatli qo\'shildi!')
            return redirect('assessment')
        else:
            messages.error(request, 'Ma\'lumotlarni to\'ldirishda xatolik!')
            return render(request, 'dashboard/assessment.html', {'form': form})

class AssessmentDetailView(View):
    """
    Bemor baholash tafsilotlari.
    """
    def get(self, request, pk):
        if not request.user.is_authenticated:
            return redirect('login')
        
        assessment = MedicalAssessment.objects.get(pk=pk)
        return render(request, 'dashboard/assessment_detail.html', {'assessment': assessment})

class AssessmentUpdateView(View):
    """
    Bemor baholashni tahrirlash.
    """
    def get(self, request, pk):
        if not request.user.is_authenticated:
            return redirect('login')
        assessment = MedicalAssessment.objects.get(pk=pk)
        form = MedicalAssessmentForm(instance=assessment)
        return render(request, 'dashboard/assessment_edit.html', {'form': form, 'assessment': assessment})

    def post(self, request, pk):
        if not request.user.is_authenticated:
            return redirect('login')
        assessment = MedicalAssessment.objects.get(pk=pk)
        form = MedicalAssessmentForm(request.POST, request.FILES, instance=assessment)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tibbiy baholash muvaffaqiyatli yangilandi!')
            return redirect('assessment_detail', pk=pk)
        else:
            messages.error(request, 'Ma\'lumotlarni to\'ldirishda xatolik!')
            return render(request, 'dashboard/assessment_edit.html', {'form': form, 'assessment': assessment})

class AssessmentDeleteView(View):
    """
    Bemor baholashni o'chirish.
    """
    def post(self, request, pk):
        if not request.user.is_authenticated:
            return redirect('login')
        assessment = MedicalAssessment.objects.get(pk=pk)
        assessment.delete()
        messages.success(request, 'Tibbiy baholash muvaffaqiyatli o\'chirildi!')
        return redirect('assessment')

class AddPatientView(View):
    """
    Yangi bemor qo'shish sahifasi.
    """
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        """
        Yangi bemor qo'shish sahifasini ko'rsatish.
        """
        # Get total patient counts for stats
        total_patients = Patient.objects.count()
        active_patients = Patient.objects.filter(status='active').count()
        pending_patients = Patient.objects.filter(status='pending').count()
        
        # Today's new patients
        today = date.today()
        today_patients = Patient.objects.filter(visit_date__date=today).count()
        
        context = {
            'stats': {
                'total': total_patients,
                'active': active_patients,
                'pending': pending_patients,
                'today': today_patients,
            }
        }
        return render(request, 'dashboard/add_patients.html', context)

    def post(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        """
        Yangi bemorni qo'shish uchun POST so'rovini qayta ishlash.
        """
        # Extract data from POST request
        full_name = request.POST.get('full_name')
        phone_number = request.POST.get('phone_number')
        date_of_birth = request.POST.get('date_of_birth')
        gender = request.POST.get('gender')
        status = request.POST.get('status', 'active')
        last_coming = request.POST.get('last_coming')
        notes = request.POST.get('additional_notes', '')

        # Calculate age if date_of_birth is provided
        age = None
        if date_of_birth:
            birth_date = date.fromisoformat(date_of_birth)
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

        # Clean phone number (remove spaces and non-digit characters)
        if phone_number:
            phone_number = ''.join(filter(str.isdigit, phone_number))
            if len(phone_number) == 9:
                phone_number = f"+998{phone_number}"

        # Create new patient
        try:
            patient = Patient.objects.create(
                full_name=full_name,
                phone_number=phone_number,
                date_of_birth=date.fromisoformat(date_of_birth) if date_of_birth else None,
                gender=gender,
                status=status,
                last_coming=date.fromisoformat(last_coming) if last_coming else None,
                notes=notes,
                age=age if age else 0,
            )
            
            messages.success(request, f"Bemor {full_name} muvaffaqiyatli qo'shildi!")
            return redirect('patient_detail', patient_id=patient.id)
            
        except Exception as e:
            messages.error(request, f"Xatolik yuz berdi: {str(e)}")
            
            # Return the entered values back to template
            context = {
                'form_data': {
                    'full_name': full_name,
                    'phone_number': phone_number,
                    'date_of_birth': date_of_birth,
                    'gender': gender,
                    'status': status,
                    'last_coming': last_coming,
                    'additional_notes': notes,
                },
                'stats': {
                    'total': Patient.objects.count(),
                    'active': Patient.objects.filter(status='active').count(),
                    'pending': Patient.objects.filter(status='pending').count(),
                    'today': Patient.objects.filter(visit_date__date=date.today()).count(),
                }
            }
            return render(request, 'dashboard/add_patients.html', context)


class PatientUpdateView(View):
    """
    Bemor ma'lumotlarini yangilash sahifasi (oddiy inputlar bilan)
    """
    def get(self, request, patient_id):
        if not request.user.is_authenticated:
            return redirect('login')
        """
        Bemor ma'lumotlarini yangilash sahifasini ko'rsatish
        """
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Format dates for HTML input type="date"
        date_of_birth = patient.date_of_birth.strftime('%Y-%m-%d') if patient.date_of_birth else ''
        last_coming = patient.last_coming.strftime('%Y-%m-%d') if patient.last_coming else ''
        
        context = {
            'patient': patient,
            'date_of_birth': date_of_birth,
            'last_coming': last_coming,
        }
        return render(request, 'dashboard/update_patient.html', context)

    def post(self, request, patient_id):
        if not request.user.is_authenticated:
            return redirect('login')
        """
        Bemor ma'lumotlarini yangilash uchun POST so'rovini qayta ishlash
        """
        patient = get_object_or_404(Patient, id=patient_id)
        
        # Extract data from POST request
        full_name = request.POST.get('full_name')
        phone_number = request.POST.get('phone_number')
        date_of_birth = request.POST.get('date_of_birth')
        gender = request.POST.get('gender')
        last_coming = request.POST.get('last_coming')
        status = request.POST.get('status')
        notes = request.POST.get('notes')
        
        # Calculate age if date_of_birth is provided
        age = None
        if date_of_birth:
            birth_date = date.fromisoformat(date_of_birth)
            today = date.today()
            age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        # Update patient fields
        patient.full_name = full_name
        patient.phone_number = phone_number
        patient.date_of_birth = date.fromisoformat(date_of_birth) if date_of_birth else None
        patient.gender = gender
        patient.last_coming = date.fromisoformat(last_coming) if last_coming else None
        patient.status = status
        patient.notes = notes
        if age is not None:
            patient.age = age
        
        try:
            patient.save()
            messages.success(request, "Bemor ma'lumotlari muvaffaqiyatli yangilandi!")
            return redirect('patient_detail', patient_id=patient.id)
        except Exception as e:
            messages.error(request, f"Xatolik yuz berdi: {str(e)}")
            
            # Return the entered values back to template
            context = {
                'patient': patient,
                'date_of_birth': date_of_birth,
                'last_coming': last_coming,
                'full_name': full_name,
                'phone_number': phone_number,
                'gender': gender,
                'status': status,
                'notes': notes,
            }
            return render(request, 'dashboard/update_patient.html', context)


class PatientDeleteView(View):

    """
    Bemorni o'chirish sahifasi.
    """
    def get(self, request, patient_id):
        if not request.user.is_authenticated:
            return redirect('login')
        """
        Bemorni o'chirish sahifasini ko'rsatish.
        """
        try:
            patient = Patient.objects.get(id=patient_id)  # Bemorni ID bo'yicha olish
            patient.delete()
            return JsonResponse({'status': 'success', 'message': 'Bemor muvaffaqiyatli o\'chirildi!'})
              # Bemorni o'chirish sahifasini ko'rsatish
        except Patient.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Bemor topilmadi!'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Xatolik yuz berdi: {str(e)}'})

def print_patient_card(request, patient_id):
    if not request.user.is_authenticated:
            return redirect('login')
    patient = get_object_or_404(Patient, id=patient_id)
    latest_assessment = MedicalAssessment.objects.filter(patient=patient).order_by('-assessment_date').first()
    
    context = {
        'patient': patient,
        'latest_assessment': latest_assessment,
        'hospital_name': "Stomatologiya Klinikasi",  # Customize this
        'current_date': datetime.now().strftime("%d.%m.%Y %H:%M"),
    }
    
    html = render_to_string('dashboard/patient_card_print.html', context)
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'filename="patient_card_{patient.id}.pdf"'
    
    # Create PDF
    pisa_status = pisa.CreatePDF(
        html, 
        dest=response,
        link_callback=lambda uri, _: os.path.join(settings.MEDIA_ROOT, uri.replace(settings.MEDIA_URL, ''))
    )
    
    if pisa_status.err:
        return HttpResponse('PDF yaratishda xatolik yuz berdi', status=500)
    return response


class PatientExportExcelView(View):
    """
    Bemorlar ro'yxatini Excel formatida eksport qilish.
    """
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        
        patients = Patient.objects.all().order_by('-visit_date')
        
        # Create an Excel file
        import pandas as pd
        from io import BytesIO

        # Prepare data for DataFrame
        data = []
        for p in patients:
            data.append({
                'ID': p.id,
                'F.I.O.': p.full_name,
                'Telefon': p.phone_number,
                'Tug\'ilgan sana': p.date_of_birth.strftime('%Y-%m-%d') if p.date_of_birth else '',
                'Jinsi': dict(M= 'Erkak', F='Ayol', O='Boshqa').get(p.gender, ''),
                'Holati': p.status,
                'Oxirgi tashrif': p.last_coming.strftime('%Y-%m-%d') if p.last_coming else '',
                'Izoh': p.notes,
                'Yoshi': p.age,
                'Tashrif sanasi': p.visit_date.strftime('%Y-%m-%d %H:%M') if p.visit_date else '',
            })
        df = pd.DataFrame(data)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Bemorlar')
        output.seek(0)

        response = HttpResponse(
            output,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="patients.xlsx"'
        return response
    

class PatientExportPDFView(View):
    """
    Bemorlar ro'yxatini PDF formatida eksport qilish.
    """
    
    def get(self, request):
        """Export patients to PDF"""
        if not request.user.is_authenticated:
            return redirect('login') 
        try:
            patients = self.filter_patients(request)
            
            if not patients.exists():
                return JsonResponse({'error': 'Eksport qilish uchun bemorlar topilmadi'}, status=400)
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer, 
                pagesize=A4, 
                rightMargin=20, 
                leftMargin=20, 
                topMargin=30, 
                bottomMargin=30
            )
            
            elements = []
            
            # Styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=18,
                spaceAfter=30,
                alignment=1,  # Center
                fontName='Helvetica-Bold'
            )
            
            subtitle_style = ParagraphStyle(
                'CustomSubtitle',
                parent=styles['Normal'],
                fontSize=12,
                spaceAfter=20,
                alignment=1,  # Center
            )
            
            # Title
            title = Paragraph("BEMORLAR RO'YXATI", title_style)
            elements.append(title)
            
            # Date range info
            date_info = self.get_date_range_info(request)
            if date_info:
                subtitle = Paragraph(date_info, subtitle_style)
                elements.append(subtitle)
            
            elements.append(Spacer(1, 20))
            
            # Prepare table data
            table_data = [
                ['№', 'F.I.Sh.', 'Tug\'ilgan sana', 'Telefon', 'Manzil', 'Kelgan sana', 'Tashxis']
            ]
            
            for idx, patient in enumerate(patients, 1):
                table_data.append([
                    str(idx),
                    patient.full_name[:25],  # Limit name length
                    patient.date_of_birth.strftime("%d.%m.%Y") if patient.date_of_birth else '',
                    patient.phone_number,
                    patient.address[:30] if hasattr(patient, 'address') and patient.address else '',  # Limit address length
                    patient.last_coming.strftime("%d.%m.%Y") if patient.last_coming else '',
                    patient.diagnosis[:20] if hasattr(patient, 'diagnosis') and patient.diagnosis else '',  # Limit diagnosis length
                ])
            
            # Create table
            table = Table(
                table_data, 
                colWidths=[0.5*inch, 2*inch, 1*inch, 1*inch, 1.5*inch, 1*inch, 1.5*inch]
            )
            
            # Table styling
            table.setStyle(TableStyle([
                # Header styling
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#366092')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                
                # Data rows styling
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                
                # Alternate row colors
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
            ]))
            
            elements.append(table)
            
            # Add summary
            elements.append(Spacer(1, 20))
            total_patients = patients.count()
            
            summary_data = [
                ['JAMI HISOBOT', '', '', ''],
                [f'Jami bemorlar soni:', f'{total_patients} ta', '', ''],
                [f'Oxirgi kelgan bemor:', f'{patients.first().full_name if patients.exists() else ""}', '', ''],
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 3*inch, 1*inch, 1*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#366092')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('GRID', (0, 0), (1, -1), 0.5, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            
            elements.append(summary_table)
            
            # Build PDF
            doc.build(elements)
            buffer.seek(0)
            
            # Generate filename
            current_date = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"bemorlar_royxati_{current_date}.pdf"
            
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as e:
            return JsonResponse({'error': f'PDF eksport xatosi: {str(e)}'}, status=500)
    
    def get_date_range_info(self, request):
        """Get date range information for PDF subtitle"""
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if date_from and date_to:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').strftime('%d.%m.%Y')
                to_date = datetime.strptime(date_to, '%Y-%m-%d').strftime('%d.%m.%Y')
                return f"Sana: {from_date} dan {to_date} gacha"
            except ValueError:
                pass
        elif date_from:
            try:
                from_date = datetime.strptime(date_from, '%Y-%m-%d').strftime('%d.%m.%Y')
                return f"Sana: {from_date} dan hozirgi kungacha"
            except ValueError:
                pass
        elif date_to:
            try:
                to_date = datetime.strptime(date_to, '%Y-%m-%d').strftime('%d.%m.%Y')
                return f"Sana: boshidan {to_date} gacha"
            except ValueError:
                pass
        
        return None
    
    def filter_patients(self, request):
        """Apply filters to patients queryset"""
        patients = Patient.objects.all()
        
        # Date range filter
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                patients = patients.filter(last_coming__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                patients = patients.filter(last_coming__lte=date_to)
            except ValueError:
                pass
        
        # Patient search filter
        patient_search = request.GET.get('patient_search')
        if patient_search:
            patients = patients.filter(
                Q(full_name__icontains=patient_search) |
                Q(phone_number__icontains=patient_search)
            )
        
        # Diagnosis filter (from MedicalAssessment)
        diagnosis = request.GET.get('diagnosis')
        if diagnosis:
            patients = patients.filter(
                medical_assessments__diagnosis__icontains=diagnosis
            ).distinct()
        
        return patients.order_by('-last_coming')