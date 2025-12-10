from django.shortcuts import render
import requests
import os
import logging
from django.urls import reverse
from django.views import View
from django.db.models import F, Sum, Case, When, DecimalField, Value
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from .models import Payment, Patient
from django.http import JsonResponse, HttpResponse, Http404
from django.core.serializers import serialize
import json
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from django.db.models.functions import Coalesce
from datetime import datetime
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from io import BytesIO
from reportlab.pdfgen import canvas


# Create your views here.

class PaymentView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return redirect('login')
        """
        Display the payment page with statistics and payment list.
        """
        # Calculate statistics
        payments = Payment.objects.all()
        today = timezone.now().date()
        
        context = {
            'total_income': payments.aggregate(total=Sum('paid_amount'))['total'] or 0,
            'total_debt': payments.aggregate(total=Sum('debt'))['total'] or 0,
            'today_payments': payments.filter(payment_date=today).aggregate(total=Sum('paid_amount'))['total'] or 0,
            'total_patients': Patient.objects.count(),
            'payments': payments.order_by('-payment_date'),
            'patients': Patient.objects.all(),
        }
        
        return render(request, 'dashboard/payments.html', context)

    def post(self, request):
        """
        Handle payment processing.
        """
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            patient_id = request.POST.get('patient')
            total_amount = float(request.POST.get('total_amount', 0))
            paid_amount = float(request.POST.get('paid_amount', 0))
            payment_method = request.POST.get('payment_method')
            
            if not patient_id or not payment_method:
                raise ValueError("Bemor va to'lov usulini tanlang")
                
            if paid_amount > total_amount:
                raise ValueError("To'langan summa umumiy summadan ko'p bo'lishi mumkin emas")
                
            patient = Patient.objects.get(id=patient_id)
            
            payment = Payment(
                patient=patient,
                total_amount=total_amount,
                paid_amount=paid_amount,
                payment_method=payment_method
            )
            payment.save()
            
            messages.success(request, "To'lov muvaffaqiyatli qo'shildi!")
            return redirect('payment')
            
        except Patient.DoesNotExist:
            messages.error(request, "Bemor topilmadi!")
        except ValueError as e:
            messages.error(request, str(e))
        except Exception as e:
            messages.error(request, f"Xatolik yuz berdi: {str(e)}")
        
        return redirect('payment')
    
class PaymentAPIView(View):
    """
    API endpoint for payment operations
    """
    def get(self, request, payment_id=None):
        if not request.user.is_authenticated:
            return redirect('login')
        if payment_id:
            # Handle single payment request (/financial/payment/<id>/)
            try:
                payment = Payment.objects.get(id=payment_id)
                data = {
                    'id': payment.id,
                    'patient_name': payment.patient.full_name,
                    'patient_phone': payment.patient.phone_number,
                    'total_amount': float(payment.total_amount),
                    'paid_amount': float(payment.paid_amount),
                    'debt': float(payment.debt),
                    'payment_method': payment.payment_method,
                    'payment_method_display': payment.get_payment_method_display(),
                    'payment_date': payment.payment_date.strftime("%d.%m.%Y"),
                }
                return JsonResponse(data)
            except Payment.DoesNotExist:
                return JsonResponse({'error': 'Payment not found'}, status=404)
        
        # Check if this is an export request
        export_type = request.GET.get('export')
        if export_type:
            return self.handle_export(request)
        
        # Default: return filtered payments as JSON
        payments = self.filter_payments(request)
        data = [
            {
                'id': p.id,
                'patient_name': p.patient.full_name,
                'patient_phone': p.patient.phone_number,
                'total_amount': float(p.total_amount),
                'paid_amount': float(p.paid_amount),
                'debt': float(p.debt),
                'payment_method': p.payment_method,
                'payment_method_display': p.get_payment_method_display(),
                'payment_date': p.payment_date.strftime("%d.%m.%Y"),
            }
            for p in payments
        ]
        return JsonResponse(data, safe=False)

    def handle_export(self, request):
        """Handle Excel and PDF export requests"""
        if not request.user.is_authenticated:
            return redirect('login')
        export_type = request.GET.get('export')
        payments = self.filter_payments(request)
        
        if export_type == 'excel':
            return self.export_to_excel(payments)
        elif export_type == 'pdf':
            return self.export_to_pdf(payments)
        else:
            return JsonResponse({'error': 'Invalid export type. Use "excel" or "pdf"'}, status=400)

    def filter_payments(self, request):
        """Apply filters to payments queryset"""
        if not request.user.is_authenticated:
            return redirect('login')
        payments = Payment.objects.all().select_related('patient')
        
        # Date range filter
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                payments = payments.filter(payment_date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                payments = payments.filter(payment_date__lte=date_to)
            except ValueError:
                pass
        
        # Payment method filter
        payment_method = request.GET.get('payment_method')
        if payment_method and payment_method in ['cash', 'card', 'online']:
            payments = payments.filter(payment_method=payment_method)
        
        # Patient search filter
        patient_search = request.GET.get('patient_search')
        if patient_search:
            payments = payments.filter(
                Q(patient__full_name__icontains=patient_search) |
                Q(patient__phone_number__icontains=patient_search)
            )
        
        return payments.order_by('-payment_date')

    def export_to_excel(self, payments):
        """Export payments data to Excel"""
        try:
            # Create a DataFrame with the data we want to export
            data = []
            for payment in payments:
                data.append({
                    'ID': payment.id,
                    'Bemor': payment.patient.full_name,
                    'Telefon': payment.patient.phone_number,
                    'Umumiy summa': float(payment.total_amount),
                    "To'langan": float(payment.paid_amount),
                    'Qarz': float(payment.debt),
                    "To'lov usuli": payment.get_payment_method_display(),
                    'Sana': payment.payment_date.strftime("%d.%m.%Y"),
                    'Holat': "To'langan" if payment.debt == 0 else "Qarzli",
                })
            
            if not data:
                return JsonResponse({'error': 'No data to export'}, status=400)
            
            df = pd.DataFrame(data)
            
            # Create HTTP response with Excel content
            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            response['Content-Disposition'] = 'attachment; filename="payments_export.xlsx"'
            
            # Write to Excel with proper formatting
            with pd.ExcelWriter(response, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="To'lovlar", index=False)
                
                # Get the workbook and worksheet
                workbook = writer.book
                worksheet = writer.sheets["To'lovlar"]
                
                # Auto-adjust column widths
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
            
            return response
            
        except Exception as e:
            return JsonResponse({'error': f'Excel export failed: {str(e)}'}, status=500)

    def export_to_pdf(self, payments):
        """Export payments data to PDF with better formatting"""
        try:
            if not payments:
                return JsonResponse({'error': 'No data to export'}, status=400)
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, 
                                  topMargin=30, bottomMargin=30)
            
            # Container for the 'Flowable' objects
            elements = []
            
            # Create styles
            styles = getSampleStyleSheet()
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=16,
                spaceAfter=30,
                alignment=1,  # Center alignment
            )
            
            # Add title
            title = Paragraph("To'lovlar ro'yxati", title_style)
            elements.append(title)
            elements.append(Spacer(1, 20))
            
            # Prepare data for table
            data = [
                ['ID', 'Bemor', 'Telefon', 'Umumiy', "To'langan", 'Qarz', 'Usul', 'Sana', 'Holat']
            ]
            
            for payment in payments:
                data.append([
                    str(payment.id),
                    payment.patient.full_name[:20],  # Limit name length
                    payment.patient.phone_number,
                    f"{float(payment.total_amount):,.0f}",
                    f"{float(payment.paid_amount):,.0f}",
                    f"{float(payment.debt):,.0f}",
                    payment.get_payment_method_display(),
                    payment.payment_date.strftime("%d.%m.%Y"),
                    "To'langan" if payment.debt == 0 else "Qarzli"
                ])
            
            # Create table
            table = Table(data, colWidths=[0.5*inch, 1.5*inch, 1*inch, 0.8*inch, 
                                         0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch])
            
            # Add style to table
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(table)
            
            # Build PDF
            doc.build(elements)
            buffer.seek(0)
            
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="payments_export.pdf"'
            return response
            
        except Exception as e:
            return JsonResponse({'error': f'PDF export failed: {str(e)}'}, status=500)

    def post(self, request):
        """Handle POST requests for creating payments"""
        return JsonResponse({'error': 'POST method not implemented'}, status=405)

    def put(self, request, payment_id):
        """Handle PUT requests for updating payments"""
        return JsonResponse({'error': 'PUT method not implemented'}, status=405)

    def delete(self, request, payment_id):
        """Handle DELETE requests for deleting payments"""
        return JsonResponse({'error': 'DELETE method not implemented'}, status=405)

class PaymentEditView(View):
    """View for editing payments"""
    def get(self, request, payment_id):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            payment = Payment.objects.get(id=payment_id)
            return render(request, 'dashboard/edit_payment.html', {
                'payment': payment,
                'patients': Patient.objects.all()  # In case you want to change patient
            })
        except Payment.DoesNotExist:
            raise Http404("To'lov topilmadi")

    def post(self, request, payment_id):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            payment = Payment.objects.get(id=payment_id)
            
            # Get form data
            total_amount = float(request.POST.get('total_amount', 0))
            paid_amount = float(request.POST.get('paid_amount', 0))
            payment_method = request.POST.get('payment_method')
            payment_date = request.POST.get('payment_date')
            note = request.POST.get('note', '')
            
            # Validate amounts
            if total_amount < 0 or paid_amount < 0:
                messages.error(request, "Summalar manfiy bo'lishi mumkin emas!")
                return redirect('edit-payment', payment_id=payment_id)
                
            if paid_amount > total_amount:
                messages.error(request, "To'langan summa umumiy summadan ko'p bo'lishi mumkin emas!")
                return redirect('edit-payment', payment_id=payment_id)
            
            # Update payment
            payment.total_amount = total_amount
            payment.paid_amount = paid_amount
            payment.payment_method = payment_method
            payment.payment_date = payment_date
            payment.save()
            
            messages.success(request, "To'lov muvaffaqiyatli yangilandi!")
            return redirect('payment')
            
        except Payment.DoesNotExist:
            messages.error(request, "To'lov topilmadi!")
            return redirect('payment')
        except ValueError:
            messages.error(request, "Noto'g'ri summa formati!")
            return redirect('edit-payment', payment_id=payment_id)
        except Exception as e:
            messages.error(request, f"Xatolik yuz berdi: {str(e)}")
            return redirect('edit-payment', payment_id=payment_id)


class PaymentAddPartialView(View):
    """View for adding partial payments to existing debt"""
    def get(self, request, payment_id):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            payment = Payment.objects.get(id=payment_id)
            patient = payment.patient
            if payment.debt <= 0:
                messages.error(request, "Bu to'lov uchun qarz mavjud emas!")
                return redirect('payments')

            # Return form for adding partial payment
            return render(request, 'dashboard/add_partial_payment.html', {
                'payment': payment,
                'patient': patient,
                'remaining_debt': payment.debt
            })
        except Payment.DoesNotExist:
            raise Http404("Payment not found")
    
    def post(self, request, payment_id):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            from decimal import Decimal
            payment = Payment.objects.get(id=payment_id)
            additional_payment = Decimal(request.POST.get('additional_payment', 0))
            
            if additional_payment <= 0:
                messages.error(request, "Noto'g'ri summa kiritildi!")
                return redirect('add-payment', payment_id=payment_id)
            
            payment.paid_amount += additional_payment
            payment.save()
            
            messages.success(request, f"{additional_payment} so'm qo'shimcha to'lov qabul qilindi!")
            return redirect('payment')
        except Payment.DoesNotExist:
            raise Http404("Payment not found")


class PaymentReceiptView(View):
    """View for generating payment receipts"""
    def get(self, request, payment_id):
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            payment = Payment.objects.get(id=payment_id)
            # Generate receipt HTML
            return render(request, 'dashboard/receipt.html', {'payment': payment})
        except Payment.DoesNotExist:
            raise Http404("Payment not found")

from django.views import View
from django.http import JsonResponse, HttpResponse
from django.db.models import Q
from datetime import datetime
from io import BytesIO
import pandas as pd
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from .models import Payment  # O'zingizning model importingiz


class PaymentExcelExportView(View):
    """
    Excel export uchun alohida API view
    URL: /api/payment/export/excel/
    """
    
    def get(self, request):
        """Export payments to Excel"""
        if not request.user.is_authenticated:
            return redirect('login')
        try:
            payments = self.filter_payments(request)
            
            if not payments.exists():
                return JsonResponse({'error': 'Eksport qilish uchun ma\'lumotlar topilmadi'}, status=400)
            
            # Create DataFrame
            data = []
            for payment in payments:
                data.append({
                    'ID': payment.id,
                    'Bemor': payment.patient.full_name,
                    'Telefon': payment.patient.phone_number,
                    'Umumiy summa (so\'m)': float(payment.total_amount),
                    "To'langan summa (so\'m)": float(payment.paid_amount),
                    'Qarz (so\'m)': float(payment.debt),
                    "To'lov usuli": payment.get_payment_method_display(),
                    'Sana': payment.payment_date.strftime("%d.%m.%Y"),
                    'Holat': "To'langan" if payment.debt == 0 else "Qarzli",
                })
            
            df = pd.DataFrame(data)
            
            # Create Excel response
            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            
            # Generate filename with current date
            current_date = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"tolovlar_royxati_{current_date}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            # Write to Excel with formatting
            with pd.ExcelWriter(response, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name="To'lovlar", index=False)
                
                # Get workbook and worksheet for formatting
                workbook = writer.book
                worksheet = writer.sheets["To'lovlar"]
                
                # Auto-adjust column widths
                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 40)
                    worksheet.column_dimensions[column_letter].width = adjusted_width
                
                # Style header row
                from openpyxl.styles import Font, PatternFill, Alignment
                header_font = Font(bold=True, color="FFFFFF")
                header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                
                for cell in worksheet[1]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = Alignment(horizontal="center", vertical="center")
            
            return response
            
        except Exception as e:
            return JsonResponse({'error': f'Excel eksport xatosi: {str(e)}'}, status=500)
    
    def filter_payments(self, request):
        """Apply filters to payments queryset"""
        if not request.user.is_authenticated:
            return redirect('login') 
        payments = Payment.objects.all().select_related('patient')
        
        # Date range filter
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                payments = payments.filter(payment_date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                payments = payments.filter(payment_date__lte=date_to)
            except ValueError:
                pass
        
        # Payment method filter
        payment_method = request.GET.get('payment_method')
        if payment_method and payment_method in ['cash', 'card', 'online']:
            payments = payments.filter(payment_method=payment_method)
        
        # Patient search filter
        patient_search = request.GET.get('patient_search')
        if patient_search:
            payments = payments.filter(
                Q(patient__full_name__icontains=patient_search) |
                Q(patient__phone_number__icontains=patient_search)
            )
        
        # Status filter
        status = request.GET.get('status')
        if status == 'paid':
            payments = payments.filter(debt=0)
        elif status == 'debt':
            payments = payments.filter(debt__gt=0)
        
        return payments.order_by('-payment_date')


class PaymentPDFExportView(View):
    """
    PDF export uchun alohida API view
    URL: /api/payment/export/pdf/
    """
    
    def get(self, request):
        """Export payments to PDF"""
        if not request.user.is_authenticated:
            return redirect('login') 
        try:
            payments = self.filter_payments(request)
            
            if not payments.exists():
                return JsonResponse({'error': 'Eksport qilish uchun ma\'lumotlar topilmadi'}, status=400)
            
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
            title = Paragraph("TO'LOVLAR RO'YXATI", title_style)
            elements.append(title)
            
            # Date range info
            date_info = self.get_date_range_info(request)
            if date_info:
                subtitle = Paragraph(date_info, subtitle_style)
                elements.append(subtitle)
            
            elements.append(Spacer(1, 20))
            
            # Prepare table data
            table_data = [
                ['№', 'Bemor', 'Telefon', 'Umumiy', "To'langan", 'Qarz', 'Usul', 'Sana', 'Holat']
            ]
            
            for idx, payment in enumerate(payments, 1):
                table_data.append([
                    str(idx),
                    payment.patient.full_name[:25],  # Limit name length
                    payment.patient.phone_number,
                    f"{float(payment.total_amount):,.0f}",
                    f"{float(payment.paid_amount):,.0f}",
                    f"{float(payment.debt):,.0f}",
                    payment.get_payment_method_display()[:10],
                    payment.payment_date.strftime("%d.%m.%Y"),
                    "To'langan" if payment.debt == 0 else "Qarzli"
                ])
            
            # Create table
            table = Table(
                table_data, 
                colWidths=[0.4*inch, 1.8*inch, 1*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch, 0.8*inch]
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
            total_amount = sum(float(p.total_amount) for p in payments)
            paid_amount = sum(float(p.paid_amount) for p in payments)
            debt_amount = sum(float(p.debt) for p in payments)
            
            summary_data = [
                ['JAMI HISOBOT', '', '', ''],
                [f'Jami to\'lovlar soni:', f'{payments.count()} ta', '', ''],
                [f'Umumiy summa:', f'{total_amount:,.0f} so\'m', '', ''],
                [f'To\'langan summa:', f'{paid_amount:,.0f} so\'m', '', ''],
                [f'Qarz summa:', f'{debt_amount:,.0f} so\'m', '', ''],
            ]
            
            summary_table = Table(summary_data, colWidths=[2*inch, 1.5*inch, 1*inch, 1*inch])
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
            filename = f"tolovlar_royxati_{current_date}.pdf"
            
            response = HttpResponse(buffer.getvalue(), content_type='application/pdf')
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            
            return response
            
        except Exception as e:
            return JsonResponse({'error': f'PDF eksport xatosi: {str(e)}'}, status=500)
    
    def get_date_range_info(self, request):
        """Get date range information for PDF subtitle"""
        if not request.user.is_authenticated:
            return redirect('login') 
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
    
    def filter_payments(self, request):
        """Apply filters to payments queryset"""
        if not request.user.is_authenticated:
            return redirect('login') 
        payments = Payment.objects.all().select_related('patient')
        
        # Date range filter
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                payments = payments.filter(payment_date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                payments = payments.filter(payment_date__lte=date_to)
            except ValueError:
                pass
        
        # Payment method filter
        payment_method = request.GET.get('payment_method')
        if payment_method and payment_method in ['cash', 'card', 'online']:
            payments = payments.filter(payment_method=payment_method)
        
        # Patient search filter
        patient_search = request.GET.get('patient_search')
        if patient_search:
            payments = payments.filter(
                Q(patient__full_name__icontains=patient_search) |
                Q(patient__phone_number__icontains=patient_search)
            )
        
        # Status filter
        status = request.GET.get('status')
        if status == 'paid':
            payments = payments.filter(debt=0)
        elif status == 'debt':
            payments = payments.filter(debt__gt=0)
        
        return payments.order_by('-payment_date')


logger = logging.getLogger(__name__)

def debt_notification_dashboard(request):
    """
    Qarz bo'yicha SMS yuborish dashboard
    """
    if not request.user.is_authenticated:
            return redirect('login')
    context = {
        'default_message': 'Hurmatli {{patient}}, sizda {{debt}} so\'m qarz bor. Iltimos to\'lovni amalga oshiring. Telefon: {{phone}}'
    }
    return render(request, 'dashboard/debt_notification.html', context)

def get_debtors_list(threshold=0):
    """
    Qarzli bemorlar ro'yxatini qaytaradi
    """
    try:
        from .models import Patient  # Model import qilish
        
        queryset = Patient.objects.annotate(
            total_debt=Sum(
                Case(
                    When(
                        payments__total_amount__gt=F('payments__paid_amount'),
                        then=F('payments__total_amount') - F('payments__paid_amount')
                    ),
                    default=Value(0),
                    output_field=DecimalField(max_digits=18, decimal_places=2)
                )
            )
        ).filter(
            total_debt__gt=threshold,
            total_debt__isnull=False,
            phone_number__isnull=False  # Telefon raqami bo'sh bo'lmasin
        ).exclude(
            phone_number__exact=''  # Bo'sh telefon raqamlarini chiqarib tashlash
        ).order_by('-total_debt').distinct()
        
        logger.info(f"Found {queryset.count()} debtors with threshold {threshold}")
        return queryset
        
    except Exception as e:
        logger.error(f"Error in get_debtors_list: {str(e)}")
        raise

@require_http_methods(["GET"])
def get_debtors_api(request):
    """
    API endpoint to get filtered debtors list
    """
    if not request.user.is_authenticated:
            return redirect('login') 
    try:
        threshold = float(request.GET.get('threshold', 0))
        logger.info(f"Getting debtors with threshold: {threshold}")
        
        debtors_queryset = get_debtors_list(threshold)
        
        # values() bilan kerakli maydonlarni olish
        debtors_data = debtors_queryset.values(
            'id', 'full_name', 'phone_number', 'total_debt'
        )
        
        logger.info(f"Queryset count: {debtors_data.count()}")
        
        debtors_list = []
        for debtor in debtors_data:
            total_debt = debtor.get('total_debt') or Decimal('0.00')
            
            debtor_info = {
                'id': debtor['id'],
                'full_name': debtor['full_name'] or 'N/A',
                'phone_number': format_phone_number(debtor['phone_number']),
                'total_debt': f"{float(total_debt):,.2f}"
            }
            debtors_list.append(debtor_info)
            logger.debug(f"Added debtor: {debtor_info['full_name']} - {debtor_info['total_debt']}")
        
        logger.info(f"Final debtors list length: {len(debtors_list)}")
        
        return JsonResponse({
            'success': True,
            'debtors': {
                'debtors_list': debtors_list  # Bu yerdagi o'zgarish
            },
            'count': len(debtors_list),
            'threshold': threshold
        })
        
    except ValueError as e:
        logger.error(f"Invalid threshold value: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Noto\'g\'ri qarz miqdori kiritildi'
        }, status=400)
        
    except Exception as e:
        logger.error(f"Error in get_debtors_api: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'Server xatosi: {str(e)}'
        }, status=500)

@require_http_methods(["POST"])
def send_debt_sms_api(request):
    """
    API endpoint to send SMS to debtors using Stase.uz
    """
    if not request.user.is_authenticated:
            return redirect('login') 
    try:
        # Ma'lumotlarni olish
        threshold = float(request.POST.get('debt_threshold', 0))
        message_template = request.POST.get('message_template', '').strip()
        
        # Validatsiya
        if not message_template:
            return JsonResponse({
                'success': False,
                'error': 'SMS shablon bo\'sh bo\'lishi mumkin emas'
            }, status=400)
        
        # Qarzdorlarni olish
        debtors = get_debtors_list(threshold).values(
            'id', 'full_name', 'phone_number', 'total_debt'
        )
        
        sent_count = 0
        failed_list = []
        
        # Har bir qarzdorga SMS yuborish
        for debtor in debtors:
            try:
                # Telefon raqamini formatlash
                phone = format_phone_number(debtor['phone_number'])
                if not phone:
                    raise ValueError("Noto'g'ri telefon raqam formati")
                
                # Xabar matnini yaratish
                message = build_sms_message(message_template, debtor)
                
                # SMS yuborish
                if send_sms(phone, message):
                    sent_count += 1
                else:
                    failed_list.append({
                        'name': debtor['full_name'],
                        'phone': phone,
                        'error': 'SMS yuborishda xato'
                    })
                    
            except Exception as e:
                failed_list.append({
                    'name': debtor['full_name'],
                    'phone': debtor['phone_number'],
                    'error': str(e)
                })
                continue
        
        # Javobni tayyorlash
        response_data = {
            'success': True,
            'sent_count': sent_count,
            'total_debtors': len(debtors),
            'message': f'{sent_count} ta SMS muvaffaqiyatli yuborildi'
        }
        
        if failed_list:
            response_data['failed_count'] = len(failed_list)
            response_data['failed_list'] = failed_list[:10]  # Faqat birinchi 10 ta xato
        
        return JsonResponse(response_data)
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'error': 'Noto\'g\'ri qarz miqdori kiritildi'
        }, status=400)
    except Exception as e:
        logger.error(f"Error in send_debt_sms_api: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Server xatosi: {str(e)}'
        }, status=500)
    

def build_sms_message(template, debtor_data):
    """
    SMS shablonini to'ldirish
    """
    try:
        total_debt = debtor_data.get('total_debt', '0.00')
        full_name = debtor_data.get('full_name', 'Bemor')
        phone_number = debtor_data.get('phone_number', '')
        
        # Qarz miqdorini formatlash
        if isinstance(total_debt, str):
            total_debt = total_debt.replace(',', '')
            try:
                total_debt = float(total_debt)
            except ValueError:
                total_debt = 0.00
        
        # Shablonni to'ldirish
        message = (
            template
            .replace('[patient]', full_name)
            .replace('[debt]', f"{total_debt:,.2f}")
            .replace('[phone]', format_phone_number(phone_number))
        )
        
        return message
        
    except Exception as e:
        logger.error(f"Error building SMS message: {str(e)}")
        return "Hurmatli mijoz, sizda qarz mavjud. Iltimos, to'lov qiling."

def send_sms(phone_number, message):
    """
    Stase.uz SMS API orqali xabar yuborish - yangilangan versiya
    """
    try:
        import requests
        from django.conf import settings
        
        # Tokenni settings.py dan olish
        SMS_TOKEN = os.environ.get('SMS_API_TOKEN', settings.SMS_TOKEN)
        
        # Telefon raqamini to'g'ri formatga keltirish (998XXXXXXXXX)
        phone = format_phone_number(phone_number).replace('+', '')
        
        # API so'rovi uchun header va payload
        headers = {
            'Authorization': f'Bearer {SMS_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "nomer": phone,
            "xabar": message,
            "token": SMS_TOKEN  # Ehtiyot bo'ling, token ikkala joyda ham yuborilmayotgan bo'lishi mumkin
        }
        
        # POST so'rovini yuborish
        response = requests.post(
            "https://sms.stase.uz/index.php",
            json=payload,
            headers=headers
        )
        
        # Javobni tekshirish
        response_data = response.json()
        
        if response.status_code == 200 and response_data.get('status') == True:
            logger.info(f"SMS sent successfully to {phone}: {response_data.get('message')}")
            return True
        else:
            error_msg = response_data.get('message', 'Noma\'lum xato')
            logger.error(f"SMS sending failed to {phone}. Status: {response.status_code}. Error: {error_msg}")
            return False
            
    except requests.exceptions.RequestException as e:
        logger.error(f"SMS request failed to {phone_number}: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
        return False
    
def format_phone_number(phone):
    """
    Telefon raqamini standart formatga keltirish (+998XXXXXXXXX)
    """
    if not phone:
        return ""
    
    # Faqat raqamlarni qoldirish
    phone = ''.join(filter(str.isdigit, str(phone)))
    
    # Formatlash
    if phone.startswith('998') and len(phone) == 12:
        return f"+{phone}"
    elif len(phone) == 9 and phone.startswith('9'):
        return f"+998{phone}"
    elif len(phone) > 9:
        return f"+998{phone[-9:]}"
    
    return ""