from django.urls import path

from .views import PaymentView, PaymentAPIView, PaymentEditView, PaymentAddPartialView, PaymentReceiptView, PaymentExcelExportView, PaymentPDFExportView, get_debtors_api, send_debt_sms_api, debt_notification_dashboard
urlpatterns = [
    path('', PaymentView.as_view(), name='payment'),  # Payment processing view
    # You can add more payment-related paths here if needed
    path('api/payment/', PaymentAPIView.as_view(), name='payment-api'),
    path('api/payment/<int:payment_id>/', PaymentAPIView.as_view(), name='payment-detail'),
    
    # Export endpoints
    path('financial/export/excel/', PaymentExcelExportView.as_view(), name='export-excel'),
    path('financial/export/pdf/', PaymentPDFExportView.as_view(), name='export-pdf'),
    path('financial/payment/<int:payment_id>/', PaymentAPIView.as_view(), name='payment-detail-api'),
    path('financial/payment/<int:payment_id>/edit/', PaymentEditView.as_view(), name='edit-payment'),
    path('financial/payment/<int:payment_id>/add-payment/', PaymentAddPartialView.as_view(), name='add-payment'),
    path('financial/payment/<int:payment_id>/receipt/', PaymentReceiptView.as_view(), name='payment-receipt'),
    path('debt-notifications/', debt_notification_dashboard, name='debt_notification'),
    path('api/debtors/', get_debtors_api, name='get_debtors_api'),
    path('api/send-debt-sms/', send_debt_sms_api, name='send_debt_sms_api'),
]