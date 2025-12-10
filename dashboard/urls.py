from django.urls import path
from .views import DashboardView, ReportsView, get_report_data, export_report, quick_report

urlpatterns = [
    path('', DashboardView.as_view(), name='home'),  # Display Dashboard page
    path('reports/', ReportsView.as_view(), name='reports'),  # Display Reports page
    path('get-report-data/', get_report_data, name='get_report_data'),
    path('export/<str:format_type>/', export_report, name='export_report'),
    path('quick/<str:period>/', quick_report, name='quick_report'),
]
