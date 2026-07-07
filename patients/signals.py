from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import GlucoseLog, LabResult, DiabetesAssessment
from .diagnosis import recompute_patient_diagnosis


@receiver(post_save, sender=GlucoseLog)
def alert_on_critical_glucose(sender, instance, created, **kwargs):
    """
    Signal handler that sends an urgent email alert to the patient's doctor
    if a glucose reading exceeds 200 mg/dL (critical threshold for gestational diabetes).
    """
    if not created:
        # Only alert on new readings, not updates
        return

    # Check if glucose level is critical (> 200 mg/dL)
    if instance.glucose_level <= 200:
        return

    # Get the patient profile
    patient_profile = instance.profile
    doctor_email = patient_profile.doctor_email

    # If no doctor email is assigned, don't send (could also send to default/admin email)
    if not doctor_email:
        return

    # Build email content
    patient_name = patient_profile.user.get_full_name() or patient_profile.user.username
    reading_value = instance.glucose_level
    reading_time = instance.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    meal_context = instance.get_meal_context_display()

    subject = f"🚨 URGENT: Critical Glucose Reading for Patient {patient_name}"

    message = f"""
Dear Doctor,

A CRITICAL glucose reading has been recorded for your patient.

PATIENT: {patient_name}
READING: {reading_value} mg/dL
TIMESTAMP: {reading_time}
MEAL CONTEXT: {meal_context}

This reading exceeds the critical threshold of 200 mg/dL and requires immediate attention.

Please contact the patient to assess their condition and provide guidance.

---
This is an automated alert from the ASTA624 PROJECT Gestational Diabetes Monitoring System.
"""

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[doctor_email],
            fail_silently=False,
        )
    except Exception as e:
        # Log error but don't crash the save operation
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send critical glucose alert email: {str(e)}")


@receiver(post_save, sender=LabResult)
def recompute_diagnosis_on_lab_save(sender, instance, **kwargs):
    if instance.patient_id:
        recompute_patient_diagnosis(instance.patient)


@receiver(post_save, sender=DiabetesAssessment)
def recompute_diagnosis_on_assessment_save(sender, instance, **kwargs):
    if instance.patient_id:
        recompute_patient_diagnosis(instance.patient)
