from django.db import models
from django.utils import timezone
from django.conf import settings


class Patient(models.Model):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('O', 'Other'),
    ]

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    email = models.EmailField(blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    emergency_contact = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Encounter(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='encounters')
    encounter_date = models.DateTimeField(default=timezone.now)
    reason = models.CharField(max_length=200)
    diagnosis = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    provider = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"Encounter {self.id} for {self.patient}"


class VitalSign(models.Model):
    encounter = models.ForeignKey(Encounter, on_delete=models.CASCADE, related_name='vital_signs')
    measurement_time = models.DateTimeField(default=timezone.now)
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    heart_rate = models.PositiveIntegerField(blank=True, null=True)
    systolic_bp = models.PositiveIntegerField(blank=True, null=True)
    diastolic_bp = models.PositiveIntegerField(blank=True, null=True)
    respiratory_rate = models.PositiveIntegerField(blank=True, null=True)
    oxygen_saturation = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)

    def __str__(self):
        return f"Vitals for {self.encounter} at {self.measurement_time}"


class Appointment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    appointment_date = models.DateTimeField()
    provider = models.CharField(max_length=100)
    purpose = models.CharField(max_length=200)
    completed = models.BooleanField(default=False)

    def __str__(self):
        return f"Appointment for {self.patient} on {self.appointment_date:%Y-%m-%d %H:%M}"


class BlogPost(models.Model):
    CATEGORY_GENERAL = 'general'
    CATEGORY_DIETICIAN = 'dietician'
    CATEGORY_NUTRITIONNIST = 'nutritionnist'
    CATEGORY_PHARMACIST = 'pharmacist'
    CATEGORY_PHYSICIAN = 'physician'
    CATEGORY_CHOICES = [
        (CATEGORY_GENERAL, 'General Blog'),
        (CATEGORY_DIETICIAN, 'Chat with a Dietician'),
        (CATEGORY_NUTRITIONNIST, 'Chat with a Nutritionnist'),
        (CATEGORY_PHARMACIST, 'Chat with a Pharmacist'),
        (CATEGORY_PHYSICIAN, 'Chat with a Physician'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True, related_name='blog_posts')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL, db_index=True)
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True)
    body = models.TextField()
    published = models.BooleanField(default=True)
    published_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-published_at']

    def get_absolute_url(self):
        from django.urls import reverse

        return reverse('patients:blog_detail', args=[self.pk])

    def __str__(self):
        return self.title


class Comment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.SET_NULL, null=True, blank=True, related_name='comments')
    post = models.ForeignKey(BlogPost, on_delete=models.CASCADE, related_name='comments')
    author_name = models.CharField(max_length=100)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Comment by {self.author_name} on {self.post.title}"


class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    patient = models.OneToOneField(Patient, null=True, blank=True, on_delete=models.SET_NULL, related_name='user_profile')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.user.username


class PatientProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='patient_profile')
    gestational_age_weeks = models.PositiveIntegerField()
    target_fasting_glucose = models.PositiveIntegerField(default=95)
    doctor_email = models.EmailField(blank=True, null=True, help_text='Email address of assigned doctor for critical alerts')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} Gestational Profile"


class GlucoseLog(models.Model):
    FASTING = 'F'
    ONE_HOUR_BREAKFAST = '1B'
    TWO_HOUR_BREAKFAST = '2B'
    ONE_HOUR_LUNCH = '1L'
    TWO_HOUR_LUNCH = '2L'
    ONE_HOUR_DINNER = '1D'
    TWO_HOUR_DINNER = '2D'

    MEAL_CONTEXT_CHOICES = [
        (FASTING, 'Fasting'),
        (ONE_HOUR_BREAKFAST, '1-Hour Post-Breakfast'),
        (TWO_HOUR_BREAKFAST, '2-Hour Post-Breakfast'),
        (ONE_HOUR_LUNCH, '1-Hour Post-Lunch'),
        (TWO_HOUR_LUNCH, '2-Hour Post-Lunch'),
        (ONE_HOUR_DINNER, '1-Hour Post-Dinner'),
        (TWO_HOUR_DINNER, '2-Hour Post-Dinner'),
    ]

    profile = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='glucose_logs')
    timestamp = models.DateTimeField()
    glucose_level = models.PositiveIntegerField(help_text='mg/dL')
    meal_context = models.CharField(max_length=3, choices=MEAL_CONTEXT_CHOICES)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['profile']),
            models.Index(fields=['timestamp']),
        ]

    def __str__(self):
        return f"{self.profile.user.username} - {self.glucose_level} mg/dL @ {self.timestamp:%Y-%m-%d %H:%M}"


class GlucosePrediction(models.Model):
    profile = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='predictions')
    predicted_value = models.IntegerField(help_text='Predicted glucose level (mg/dL)')
    target_timestamp = models.DateTimeField(help_text='The timestamp this prediction is for')
    model = models.CharField(max_length=50, default='moving_average')
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-target_timestamp']
        indexes = [
            models.Index(fields=['profile']),
            models.Index(fields=['target_timestamp']),
        ]

    def __str__(self):
        return f"Prediction for {self.profile.user.username} @ {self.target_timestamp:%Y-%m-%d}: {self.predicted_value} mg/dL"


class DoctorAlert(models.Model):
    SPIKE = 'spike'
    ANOMALY = 'anomaly'
    ALERT_TYPE_CHOICES = [
        (SPIKE, 'Glycemic spike detected'),
        (ANOMALY, 'Statistical anomaly detected'),
    ]

    patient_profile = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='doctor_alerts')
    glucose_log = models.ForeignKey(GlucoseLog, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPE_CHOICES)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient_profile']),
            models.Index(fields=['is_read']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Alert for {self.patient_profile.user.username}: {self.get_alert_type_display()}"


class MedicationLog(models.Model):
    BEFORE_BREAKFAST = 'before_breakfast'
    AFTER_BREAKFAST = 'after_breakfast'
    BEFORE_LUNCH = 'before_lunch'
    AFTER_LUNCH = 'after_lunch'
    BEFORE_DINNER = 'before_dinner'
    AFTER_DINNER = 'after_dinner'
    BEDTIME = 'bedtime'

    SCHEDULED_TIME_CHOICES = [
        (BEFORE_BREAKFAST, 'Before Breakfast'),
        (AFTER_BREAKFAST, 'After Breakfast'),
        (BEFORE_LUNCH, 'Before Lunch'),
        (AFTER_LUNCH, 'After Lunch'),
        (BEFORE_DINNER, 'Before Dinner'),
        (AFTER_DINNER, 'After Dinner'),
        (BEDTIME, 'Bedtime'),
    ]

    profile = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name='medications')
    medication_name = models.CharField(max_length=100, help_text='e.g., Insulin Aspart, Metformin')
    dosage = models.CharField(max_length=100, help_text='e.g., 10 units, 500mg')
    scheduled_time = models.CharField(max_length=20, choices=SCHEDULED_TIME_CHOICES)
    taken = models.BooleanField(default=False)
    date = models.DateField(default=timezone.now, help_text='Date of medication schedule')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date', 'scheduled_time']
        indexes = [
            models.Index(fields=['profile', 'date']),
            models.Index(fields=['date']),
        ]
        unique_together = [['profile', 'medication_name', 'scheduled_time', 'date']]

    def __str__(self):
        return f"{self.medication_name} ({self.dosage}) - {self.get_scheduled_time_display()} on {self.date}"


class Prescription(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='prescriptions')
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['patient']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.patient} - {self.title}"


class LabResult(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='lab_results')
    test_name = models.CharField(max_length=150)
    result_value = models.CharField(max_length=100)
    unit = models.CharField(max_length=50, blank=True)
    reference_range = models.CharField(max_length=100, blank=True)
    collected_at = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-collected_at']
        indexes = [
            models.Index(fields=['patient']),
            models.Index(fields=['collected_at']),
        ]

    def __str__(self):
        return f"{self.patient} - {self.test_name}: {self.result_value}"


class DiabetesAssessment(models.Model):
    TYPE_DIABETES = 'diabetes'
    TYPE_PREDIABETES = 'prediabetes'
    TYPE_RISK = 'risk'
    ASSESSMENT_TYPE_CHOICES = [
        (TYPE_DIABETES, 'Patient with Diabetes'),
        (TYPE_PREDIABETES, 'Patient with Prediabetes'),
        (TYPE_RISK, 'Risk of Developing Diabetes'),
    ]

    DIABETES_TYPE_1 = 'type1'
    DIABETES_TYPE_2 = 'type2'
    DIABETES_GESTATIONAL = 'gestational'
    DIABETES_TYPE_CHOICES = [
        (DIABETES_TYPE_1, 'Type 1'),
        (DIABETES_TYPE_2, 'Type 2'),
        (DIABETES_GESTATIONAL, 'Gestational Diabetes'),
    ]

    ACTIVITY_HIGH = 'high'
    ACTIVITY_MODERATE = 'moderate'
    ACTIVITY_LOW = 'low'
    ACTIVITY_CHOICES = [
        (ACTIVITY_HIGH, 'High'),
        (ACTIVITY_MODERATE, 'Moderate'),
        (ACTIVITY_LOW, 'Low'),
    ]

    READINESS_LOW = 'low'
    READINESS_MEDIUM = 'medium'
    READINESS_HIGH = 'high'
    READINESS_CHOICES = [
        (READINESS_LOW, 'Low'),
        (READINESS_MEDIUM, 'Moderate'),
        (READINESS_HIGH, 'High'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='diabetes_assessments')
    assessment_type = models.CharField(max_length=20, choices=ASSESSMENT_TYPE_CHOICES)
    diabetes_type = models.CharField(max_length=20, choices=DIABETES_TYPE_CHOICES, blank=True)

    fasting_glucose = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    post_meal_glucose = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    hba1c = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    classic_hyperglycemia_symptoms = models.BooleanField(blank=True, null=True)

    insulin_use = models.BooleanField(blank=True, null=True)
    oral_medication_use = models.BooleanField(blank=True, null=True)
    medication_timing = models.TextField(blank=True)
    current_medications = models.TextField(blank=True)

    weight_kg = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    height_cm = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    bmi = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    waist_circumference_cm = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)

    medical_history = models.TextField(blank=True)
    family_history_diabetes = models.BooleanField(blank=True, null=True)
    high_bp_history = models.BooleanField(blank=True, null=True)
    high_cholesterol_history = models.BooleanField(blank=True, null=True)
    gestational_diabetes_history = models.BooleanField(blank=True, null=True)
    pcos_history = models.BooleanField(blank=True, null=True)

    dietary_habits = models.TextField(blank=True)
    eating_habits = models.TextField(blank=True)
    nutrition_assessment = models.TextField(blank=True)
    food_allergies_or_intolerance = models.TextField(blank=True)
    food_affordability_and_preparation = models.TextField(blank=True)
    food_preference_and_culture = models.TextField(blank=True)

    physical_activity_level = models.CharField(max_length=20, choices=ACTIVITY_CHOICES, blank=True)
    lifestyle_factors = models.TextField(blank=True)
    sleep_quality = models.TextField(blank=True)
    stress_level = models.TextField(blank=True)
    alcohol_intake = models.TextField(blank=True)
    smoking_status = models.TextField(blank=True)
    work_schedule = models.TextField(blank=True)
    occupation = models.CharField(max_length=100, blank=True)

    laboratory_results_summary = models.TextField(blank=True)
    readiness_to_change = models.CharField(max_length=10, choices=READINESS_CHOICES, blank=True)

    assessed_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-assessed_at']
        indexes = [
            models.Index(fields=['patient']),
            models.Index(fields=['assessment_type']),
            models.Index(fields=['assessed_at']),
        ]

    def __str__(self):
        return f"{self.patient} - {self.get_assessment_type_display()} assessment"


class DiabetesDiagnosisSummary(models.Model):
    STATUS_NORMAL = 'normal'
    STATUS_PREDIABETES = 'prediabetes'
    STATUS_DIABETES = 'diabetes'
    STATUS_INDETERMINATE = 'indeterminate'
    STATUS_CHOICES = [
        (STATUS_NORMAL, 'Normal'),
        (STATUS_PREDIABETES, 'Prediabetes'),
        (STATUS_DIABETES, 'Diabetes'),
        (STATUS_INDETERMINATE, 'Indeterminate'),
    ]

    CONFIRMED = 'confirmed'
    PROVISIONAL = 'provisional'
    NOT_APPLICABLE = 'not_applicable'
    CONFIRMATION_CHOICES = [
        (CONFIRMED, 'Confirmed'),
        (PROVISIONAL, 'Provisional'),
        (NOT_APPLICABLE, 'Not applicable'),
    ]

    patient = models.OneToOneField(Patient, on_delete=models.CASCADE, related_name='diagnosis_summary')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_INDETERMINATE)
    confirmation_status = models.CharField(max_length=20, choices=CONFIRMATION_CHOICES, default=NOT_APPLICABLE)
    reason = models.TextField(blank=True)

    fasting_plasma_glucose = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    hba1c = models.DecimalField(max_digits=4, decimal_places=2, blank=True, null=True)
    random_plasma_glucose = models.DecimalField(max_digits=6, decimal_places=2, blank=True, null=True)
    has_classic_symptoms = models.BooleanField(blank=True, null=True)

    source_assessment = models.ForeignKey(DiabetesAssessment, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_diagnoses')
    source_fpg_lab = models.ForeignKey(LabResult, on_delete=models.SET_NULL, null=True, blank=True, related_name='diagnosis_as_fpg')
    source_hba1c_lab = models.ForeignKey(LabResult, on_delete=models.SET_NULL, null=True, blank=True, related_name='diagnosis_as_hba1c')
    source_rpg_lab = models.ForeignKey(LabResult, on_delete=models.SET_NULL, null=True, blank=True, related_name='diagnosis_as_rpg')

    evaluated_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['evaluated_at']),
        ]

    def __str__(self):
        return f"{self.patient} - {self.get_status_display()} ({self.get_confirmation_status_display()})"


class EducationalContent(models.Model):
    CATEGORY_DIET = 'Diet'
    CATEGORY_EXERCISE = 'Exercise'
    CATEGORY_INSULIN = 'Insulin Management'
    CATEGORY_CARB = 'Carbohydrate Counting'
    CATEGORY_GENERAL = 'General'

    CATEGORY_CHOICES = [
        (CATEGORY_DIET, 'Diet'),
        (CATEGORY_EXERCISE, 'Exercise'),
        (CATEGORY_INSULIN, 'Insulin Management'),
        (CATEGORY_CARB, 'Carbohydrate Counting'),
        (CATEGORY_GENERAL, 'General'),
    ]

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES, default=CATEGORY_GENERAL)
    content = models.TextField()
    published = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.category})"
