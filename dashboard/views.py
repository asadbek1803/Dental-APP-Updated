import csv
import xlwt
from django.shortcuts import render, redirect
from django.views import View
from patients.models import Patient, MedicalAssessment, MedicalRecord
from payments.models import Payment
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Sum, Avg, Q
from django.utils import timezone
from datetime import timedelta, date
from patients.models import Patient, MedicalAssessment, MedicalRecord
from payments.models import Payment
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors




# Create your views here.
class DashboardView(View):
    """
    Dashboard sahifasi.
    """
    def get(self, request):
        """
        Dashboard sahifasini ko'rsatish.
        """
        if not request.user.is_authenticated:
            return redirect('login')
        
        # Dashboard uchun kerakli ma'lumotlarni olish
       
        
        # Asosiy statistikalar
        today = date.today()
        today_patients = Patient.objects.filter(last_coming=today).count()
        all_patients = Patient.objects.count()
        all_caries_medical_assessments = MedicalAssessment.objects.filter(
            patient_condition='caries'
        ).count()
        payments_today_sum = Payment.objects.filter(
            payment_date=today
        ).aggregate(total_amount=Sum('paid_amount'))['total_amount'] or 0
        
        # Filterlash uchun parametrlarni olish
        search_query = request.GET.get('search', '').strip()
        age_filter = request.GET.get('age_filter', '')
        gender_filter = request.GET.get('gender_filter', '')
        
        # Bemorlarni filterlash
        patients_queryset = Patient.objects.all()
        
        # Qidiruv bo'yicha filterlash
        if search_query:
            patients_queryset = patients_queryset.filter(
                Q(full_name__icontains=search_query) |
                Q(phone_number__icontains=search_query)
            )
        
        # Yosh guruhi bo'yicha filterlash
        if age_filter:
            if age_filter == 'child':
                patients_queryset = patients_queryset.filter(age__lte=12)
            elif age_filter == 'youth':
                patients_queryset = patients_queryset.filter(age__gte=13, age__lte=25)
            elif age_filter == 'adult':
                patients_queryset = patients_queryset.filter(age__gte=26, age__lte=60)
            elif age_filter == 'elderly':
                patients_queryset = patients_queryset.filter(age__gte=61)
        
        # Jins bo'yicha filterlash
        if gender_filter:
            patients_queryset = patients_queryset.filter(gender=gender_filter)
        
        # Eng so'nggi bemorlarni olish (filterlangan)
        last_five_patients = patients_queryset.order_by('-last_coming')[:10]
        
        data = {
            'user': request.user,
            'message': 'Dashboardga xush kelibsiz!',
            'today_patients': today_patients,
            'all_patients': all_patients,
            'all_caries_medical_assessments': all_caries_medical_assessments,
            'payments_today_sum': payments_today_sum,
            'last_five_patients': last_five_patients,
            # Filter qiymatlari
            'search_query': search_query,
            'age_filter': age_filter,
            'gender_filter': gender_filter,
        }
        
        return render(request, 'dashboard/dashboard.html', data)

class ReportsView(View):
    """
    Hisobotlar sahifasi.
    """
    def get(self, request):

        """
        Hisobotlar sahifasini ko'rsatish.
        """
        if not request.user.is_authenticated:
            return redirect('login')
        return render(request, 'dashboard/report.html')  # Hisobotlar sahifasini ko'rsatish
    


def reports_dashboard(request):

    # Calculate statistics
    if not request.user.is_authenticated:
        return redirect('login')
    total_patients = Patient.objects.count()
    total_consultations = MedicalAssessment.objects.count()
    total_prescriptions = MedicalAssessment.objects.filter(~Q(treatment_plan='')).count()
    emergency_cases = MedicalAssessment.objects.filter(patient_condition='other').count()
    total_revenue = Payment.objects.aggregate(total=Sum('paid_amount'))['total'] or 0
    
    # Calculate satisfaction rate (placeholder - would need actual feedback data)
    satisfaction_rate = 92
    
    # Calculate averages
    daily_avg_patients = round(Patient.objects.filter(
        visit_date__gte=timezone.now()-timedelta(days=30)
    ).count() / 30, 1)
    
    avg_waiting_time = 15  # Placeholder - would need actual timing data
    repeat_visits = 35  # Placeholder - would need actual visit tracking
    
    context = {
        'total_patients': total_patients,
        'total_consultations': total_consultations,
        'total_prescriptions': total_prescriptions,
        'emergency_cases': emergency_cases,
        'total_revenue': int(total_revenue / 1000),  # Convert to thousands
        'satisfaction_rate': satisfaction_rate,
        'daily_avg_patients': daily_avg_patients,
        'avg_waiting_time': avg_waiting_time,
        'repeat_visits': repeat_visits,
        'doctors': Patient.objects.filter(gender='M').order_by('full_name'),  # Simplified doctor list
    }
    return render(request, 'reports/reports.html', context)

def get_report_data(request):
    if not request.user.is_authenticated:
        return redirect('login')
    report_type = request.GET.get('report_type', 'general')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    doctor_id = request.GET.get('doctor')
    
    # Create base querysets
    payments = Payment.objects.all()
    patients = Patient.objects.all()
    assessments = MedicalAssessment.objects.all()
    
    # Apply date filters if provided
    if date_from and date_to:
        payments = payments.filter(payment_date__range=[date_from, date_to])
        patients = patients.filter(visit_date__range=[date_from, date_to])
        assessments = assessments.filter(assessment_date__range=[date_from, date_to])
    
    # Apply doctor filter if provided
    if doctor_id:
        assessments = assessments.filter(patient__id=doctor_id)
    
    # Generate different report data based on type
    if report_type == 'financial':
        data = payments.values('payment_date').annotate(
            total_amount=Sum('total_amount'),
            paid_amount=Sum('paid_amount'),
            debt=Sum('debt'),
            count=Count('id')
        ).order_by('payment_date')
    elif report_type == 'medical':
        data = assessments.values('assessment_date').annotate(
            count=Count('id'),
            caries=Count('id', filter=Q(patient_condition='caries')),
            periodontitis=Count('id', filter=Q(patient_condition='periodontitis')),
            gingivitis=Count('id', filter=Q(patient_condition='gingivitis')),
            other=Count('id', filter=Q(patient_condition='other'))
        ).order_by('assessment_date')
    elif report_type == 'patient':
        data = patients.values('visit_date').annotate(
            count=Count('id'),
            male=Count('id', filter=Q(gender='M')),
            female=Count('id', filter=Q(gender='F')),
            other_gender=Count('id', filter=Q(gender='O'))
        ).order_by('visit_date')
    else:  # general report
        data = {
            'payments': list(payments.values('payment_date', 'total_amount', 'paid_amount', 'debt').order_by('-payment_date')[:10]),
            'patients': list(patients.values('full_name', 'visit_date', 'gender', 'age').order_by('-visit_date')[:10]),
            'assessments': list(assessments.values('patient__full_name', 'assessment_date', 'patient_condition').order_by('-assessment_date')[:10]),
        }
    
    return JsonResponse({'data': data})

def export_report(request, format_type):
    if not request.user.is_authenticated:
        return redirect('login')
    report_type = request.GET.get('type', 'general')
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    
    # Get filtered data
    response_data = get_report_data(request).content
    data = JsonResponse(response_data).json()['data']
    
    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{report_type}_report.csv"'
        
        writer = csv.writer(response)
        
        if report_type == 'financial':
            writer.writerow(['Date', 'Total Amount', 'Paid Amount', 'Debt', 'Count'])
            for item in data:
                writer.writerow([
                    item['payment_date'],
                    item['total_amount'],
                    item['paid_amount'],
                    item['debt'],
                    item['count']
                ])
        elif report_type == 'medical':
            writer.writerow(['Date', 'Total', 'Caries', 'Periodontitis', 'Gingivitis', 'Other'])
            for item in data:
                writer.writerow([
                    item['assessment_date'],
                    item['count'],
                    item['caries'],
                    item['periodontitis'],
                    item['gingivitis'],
                    item['other']
                ])
        elif report_type == 'patient':
            writer.writerow(['Date', 'Total', 'Male', 'Female', 'Other Gender'])
            for item in data:
                writer.writerow([
                    item['visit_date'],
                    item['count'],
                    item['male'],
                    item['female'],
                    item['other_gender']
                ])
        else:
            writer.writerow(['General Report'])
            writer.writerow([])
            writer.writerow(['Recent Payments'])
            writer.writerow(['Date', 'Total', 'Paid', 'Debt'])
            for item in data['payments']:
                writer.writerow([
                    item['payment_date'],
                    item['total_amount'],
                    item['paid_amount'],
                    item['debt']
                ])
            writer.writerow([])
            writer.writerow(['Recent Patients'])
            writer.writerow(['Name', 'Visit Date', 'Gender', 'Age'])
            for item in data['patients']:
                writer.writerow([
                    item['full_name'],
                    item['visit_date'],
                    item['gender'],
                    item['age']
                ])
        return response
    
    elif format_type == 'excel':
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = f'attachment; filename="{report_type}_report.xls"'
        
        wb = xlwt.Workbook(encoding='utf-8')
        ws = wb.add_sheet('Report')
        
        row_num = 0
        font_style = xlwt.XFStyle()
        font_style.font.bold = True
        
        if report_type == 'financial':
            columns = ['Date', 'Total Amount', 'Paid Amount', 'Debt', 'Count']
            for col_num, column_title in enumerate(columns):
                ws.write(row_num, col_num, column_title, font_style)
            
            font_style = xlwt.XFStyle()
            for row in data:
                row_num += 1
                ws.write(row_num, 0, row['payment_date'], font_style)
                ws.write(row_num, 1, row['total_amount'], font_style)
                ws.write(row_num, 2, row['paid_amount'], font_style)
                ws.write(row_num, 3, row['debt'], font_style)
                ws.write(row_num, 4, row['count'], font_style)
        
        wb.save(response)
        return response
    
    elif format_type == 'pdf':
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{report_type}_report.pdf"'
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"{report_type.capitalize()} Report", styles['Title']))
        
        if report_type == 'financial':
            data = [['Date', 'Total', 'Paid', 'Debt', 'Count']]
            for item in data:
                data.append([
                    item['payment_date'],
                    item['total_amount'],
                    item['paid_amount'],
                    item['debt'],
                    item['count']
                ])
        elif report_type == 'medical':
            data = [['Date', 'Total', 'Caries', 'Periodontitis', 'Gingivitis', 'Other']]
            for item in data:
                data.append([
                    item['assessment_date'],
                    item['count'],
                    item['caries'],
                    item['periodontitis'],
                    item['gingivitis'],
                    item['other']
                ])
        elif report_type == 'patient':
            data = [['Date', 'Total', 'Male', 'Female', 'Other']]
            for item in data:
                data.append([
                    item['visit_date'],
                    item['count'],
                    item['male'],
                    item['female'],
                    item['other_gender']
                ])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('FONTSIZE', (0,0), (-1,0), 14),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        
        elements.append(table)
        doc.build(elements)
        
        pdf = buffer.getvalue()
        buffer.close()
        response.write(pdf)
        
        return response

def quick_report(request, period):
    # Calculate date ranges based on period
    if not request.user.is_authenticated:
        return redirect('login')
    today = timezone.now().date()
    if period == 'daily':
        date_from = today
        date_to = today
    elif period == 'weekly':
        date_from = today - timedelta(days=today.weekday())
        date_to = date_from + timedelta(days=6)
    elif period == 'monthly':
        date_from = today.replace(day=1)
        next_month = today.replace(day=28) + timedelta(days=4)
        date_to = next_month - timedelta(days=next_month.day)
    else:  # yearly
        date_from = today.replace(month=1, day=1)
        date_to = today.replace(month=12, day=31)
    
    # Get data for the period
    payments = Payment.objects.filter(payment_date__range=[date_from, date_to])
    patients = Patient.objects.filter(visit_date__range=[date_from, date_to])
    assessments = MedicalAssessment.objects.filter(assessment_date__range=[date_from, date_to])
    
    # Calculate metrics
    total_revenue = payments.aggregate(total=Sum('paid_amount'))['total'] or 0
    total_patients = patients.count()
    total_consultations = assessments.count()
    
    common_conditions = assessments.values('patient_condition').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    context = {
        'period': period,
        'date_from': date_from,
        'date_to': date_to,
        'total_revenue': total_revenue,
        'total_patients': total_patients,
        'total_consultations': total_consultations,
        'common_conditions': common_conditions,
    }
    
    return render(request, 'reports/quick_report.html', context)