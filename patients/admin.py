from django.contrib import admin
from .models import (
    Patient,
    Encounter,
    VitalSign,
    Appointment,
    BlogPost,
    Comment,
    UserProfile,
    PatientProfile,
    GlucoseLog,
    GlucosePrediction,
    DoctorAlert,
    MedicationLog,
    LabResult,
    DiabetesAssessment,
    DiabetesDiagnosisSummary,
)


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'date_of_birth', 'gender', 'email')
    search_fields = ('first_name', 'last_name', 'email')


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ('patient', 'encounter_date', 'provider', 'reason')
    list_filter = ('encounter_date', 'provider')
    search_fields = ('patient__first_name', 'patient__last_name', 'reason', 'diagnosis')


@admin.register(VitalSign)
class VitalSignAdmin(admin.ModelAdmin):
    list_display = ('encounter', 'measurement_time', 'temperature_c', 'heart_rate', 'systolic_bp', 'diastolic_bp')
    list_filter = ('measurement_time',)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'appointment_date', 'provider', 'completed')
    list_filter = ('appointment_date', 'completed')
    search_fields = ('patient__first_name', 'patient__last_name', 'provider', 'purpose')


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 1


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'published', 'published_at')
    prepopulated_fields = {'slug': ('title',)}
    inlines = [CommentInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ('post', 'author_name', 'created_at')
    search_fields = ('author_name', 'content', 'post__title')


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'patient')


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'gestational_age_weeks', 'target_fasting_glucose', 'doctor_email')
    search_fields = ('user__username', 'user__email', 'doctor_email')
    fields = ('user', 'gestational_age_weeks', 'target_fasting_glucose', 'doctor_email', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(GlucoseLog)
class GlucoseLogAdmin(admin.ModelAdmin):
    list_display = ('profile', 'timestamp', 'glucose_level', 'meal_context', 'created_at')
    list_filter = ('meal_context', 'created_at')
    search_fields = ('profile__user__username',)
    readonly_fields = ('created_at',)


@admin.register(GlucosePrediction)
class GlucosePredictionAdmin(admin.ModelAdmin):
    list_display = ('profile', 'target_timestamp', 'predicted_value', 'model')
    list_filter = ('model', 'created_at')
    search_fields = ('profile__user__username',)


@admin.register(DoctorAlert)
class DoctorAlertAdmin(admin.ModelAdmin):
    list_display = ('patient_profile', 'alert_type', 'glucose_log', 'is_read', 'created_at')
    list_filter = ('alert_type', 'is_read', 'created_at')
    search_fields = ('patient_profile__user__username', 'message')
    readonly_fields = ('created_at',)


@admin.register(MedicationLog)
class MedicationLogAdmin(admin.ModelAdmin):
    list_display = ('profile', 'medication_name', 'dosage', 'scheduled_time', 'taken', 'date')
    list_filter = ('scheduled_time', 'taken', 'date')
    search_fields = ('profile__user__username', 'medication_name')
    readonly_fields = ('created_at', 'updated_at')
    fields = ('profile', 'medication_name', 'dosage', 'scheduled_time', 'date', 'taken', 'created_at', 'updated_at')


@admin.register(LabResult)
class LabResultAdmin(admin.ModelAdmin):
    list_display = ('patient', 'test_name', 'result_value', 'unit', 'collected_at')
    list_filter = ('collected_at',)
    search_fields = ('patient__first_name', 'patient__last_name', 'test_name')


@admin.register(DiabetesAssessment)
class DiabetesAssessmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'assessment_type', 'diabetes_type', 'fasting_glucose', 'hba1c', 'assessed_at')
    list_filter = ('assessment_type', 'physical_activity_level', 'assessed_at')
    search_fields = ('patient__first_name', 'patient__last_name', 'current_medications', 'medical_history')


@admin.register(DiabetesDiagnosisSummary)
class DiabetesDiagnosisSummaryAdmin(admin.ModelAdmin):
    list_display = ('patient', 'status', 'confirmation_status', 'fasting_plasma_glucose', 'hba1c', 'random_plasma_glucose', 'evaluated_at')
    list_filter = ('status', 'confirmation_status', 'evaluated_at')
    search_fields = ('patient__first_name', 'patient__last_name', 'reason')

