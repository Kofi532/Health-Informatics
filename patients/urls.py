from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'patients'

urlpatterns = [
    path('', views.pwa_app, name='pwa_app'),
    path('patients/<int:pk>/', views.patient_detail, name='patient_detail'),
    path('patients/<int:pk>/research/', views.researcher_patient_detail, name='researcher_patient_detail'),
    path('research/', views.researcher_patient_list, name='researcher_patient_list'),
    path('research/export/', views.export_research_excel, name='export_research_excel'),
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<int:pk>/', views.blog_detail, name='blog_detail'),
    path('prescription/', views.prescription_entry, name='prescription_entry'),
    path('lab/', views.lab_result_entry, name='lab_result_entry'),
    path('assessment/', views.diabetes_assessment_entry, name='diabetes_assessment_entry'),
    path('glucose-log/', views.glucose_log_entry, name='glucose_log_entry'),
    path('dashboard/', views.patient_dashboard, name='patient_dashboard'),
    path('dashboard/approved-physicians/', views.update_approved_physicians, name='update_approved_physicians'),
    path('dashboard/approved-dieticians/', views.update_approved_dieticians, name='update_approved_dieticians'),
    path('export/deidentified/', views.export_deidentified_csv, name='export_deidentified_csv'),
    path('doctor/', views.doctor_dashboard, name='doctor_dashboard'),
    path('medication/<int:medication_id>/toggle/', views.update_medication_status, name='update_medication_status'),
    path('signup/', views.signup, name='signup'),
    path('privacy/', views.privacy_notice, name='privacy'),
    path('terms/', views.terms_of_use, name='terms'),
    path('login/', views.RoleBasedLoginView.as_view(), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='patients:login'), name='logout'),
]
