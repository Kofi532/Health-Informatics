from django import forms
from django.utils import timezone
from datetime import datetime
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import GlucoseLog, MedicationLog, Prescription, LabResult, DiabetesAssessment, UserProfile
from django.forms import inlineformset_factory, modelformset_factory


class GlucoseLogForm(forms.ModelForm):
    # split date/time for easier input on mobile/desktop
    date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}))

    class Meta:
        model = GlucoseLog
        # timestamp is composed from date+time fields
        fields = ['date', 'time', 'glucose_level', 'meal_context']
        widgets = {
            'glucose_level': forms.NumberInput(attrs={'min': 0, 'list': 'glucose-presets'}),
            'meal_context': forms.Select(),
        }
        labels = {
            'date': 'Date',
            'time': 'Time',
            'glucose_level': 'Glucose level (mg/dL)',
            'meal_context': 'Meal context',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        now = timezone.localtime()
        # sensible defaults
        self.fields['date'].initial = now.date()
        self.fields['time'].initial = now.time().replace(microsecond=0)

    def save(self, commit=True):
        instance = super().save(commit=False)
        date = self.cleaned_data.get('date')
        time = self.cleaned_data.get('time')
        if date and time:
            dt = datetime.combine(date, time)
            # make aware using Django timezone
            instance.timestamp = timezone.make_aware(dt)
        if commit:
            instance.save()
        return instance


class MedicationLogForm(forms.ModelForm):
    class Meta:
        model = MedicationLog
        fields = ['medication_name', 'dosage', 'scheduled_time', 'taken']
        widgets = {
            'medication_name': forms.TextInput(attrs={'placeholder': 'e.g., Insulin Aspart', 'class': 'form-control'}),
            'dosage': forms.TextInput(attrs={'placeholder': 'e.g., 10 units', 'class': 'form-control'}),
            'scheduled_time': forms.Select(attrs={'class': 'form-control'}),
            'taken': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class MedicationChecklistForm(forms.ModelForm):
    """Simple form to toggle medication 'taken' status."""
    class Meta:
        model = MedicationLog
        fields = ['taken']
        widgets = {
            'taken': forms.CheckboxInput(attrs={'class': 'medication-checkbox'}),
        }


class PrescriptionForm(forms.ModelForm):
    class Meta:
        model = Prescription
        fields = ['title', 'content']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Prescription title'}),
            'content': forms.Textarea(attrs={'class': 'form-control', 'rows': 6, 'placeholder': 'Enter prescription details'}),
        }


class LabResultForm(forms.ModelForm):
    collected_at = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )

    class Meta:
        model = LabResult
        fields = ['test_name', 'result_value', 'unit', 'reference_range', 'collected_at', 'notes']
        widgets = {
            'test_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., HbA1c, Hemoglobin, Serum Creatinine'}),
            'result_value': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 6.2, Negative, 98'}),
            'unit': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., %, g/dL, mg/dL'}),
            'reference_range': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 4.0 - 5.6%'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Optional notes or interpretation'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['collected_at'].initial = timezone.localtime().strftime('%Y-%m-%dT%H:%M')

    def clean_collected_at(self):
        collected_at = self.cleaned_data['collected_at']
        if timezone.is_naive(collected_at):
            return timezone.make_aware(collected_at, timezone.get_current_timezone())
        return collected_at


class DiabetesAssessmentForm(forms.ModelForm):
    assessed_at = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'})
    )

    class Meta:
        model = DiabetesAssessment
        fields = [
            'assessment_type', 'diabetes_type',
            'fasting_glucose', 'post_meal_glucose', 'hba1c', 'classic_hyperglycemia_symptoms',
            'insulin_use', 'oral_medication_use', 'medication_timing', 'current_medications',
            'weight_kg', 'height_cm', 'bmi', 'waist_circumference_cm',
            'medical_history', 'family_history_diabetes', 'high_bp_history', 'high_cholesterol_history',
            'gestational_diabetes_history', 'pcos_history',
            'dietary_habits', 'eating_habits', 'nutrition_assessment',
            'food_allergies_or_intolerance', 'food_affordability_and_preparation', 'food_preference_and_culture',
            'physical_activity_level', 'lifestyle_factors', 'sleep_quality', 'stress_level', 'alcohol_intake',
            'smoking_status', 'work_schedule', 'occupation',
            'laboratory_results_summary', 'readiness_to_change', 'assessed_at',
        ]
        widgets = {
            'assessment_type': forms.Select(attrs={'class': 'form-control'}),
            'diabetes_type': forms.Select(attrs={'class': 'form-control'}),
            'fasting_glucose': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'post_meal_glucose': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'hba1c': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'classic_hyperglycemia_symptoms': forms.Select(attrs={'class': 'form-control'}, choices=[('', 'Unknown'), (True, 'Yes'), (False, 'No')]),
            'insulin_use': forms.Select(attrs={'class': 'form-control'}, choices=[('', 'Unknown'), (True, 'Yes'), (False, 'No')]),
            'oral_medication_use': forms.Select(attrs={'class': 'form-control'}, choices=[('', 'Unknown'), (True, 'Yes'), (False, 'No')]),
            'medication_timing': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'current_medications': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'weight_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'height_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'bmi': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'waist_circumference_cm': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'medical_history': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'family_history_diabetes': forms.Select(attrs={'class': 'form-control'}, choices=[('', 'Unknown'), (True, 'Yes'), (False, 'No')]),
            'high_bp_history': forms.Select(attrs={'class': 'form-control'}, choices=[('', 'Unknown'), (True, 'Yes'), (False, 'No')]),
            'high_cholesterol_history': forms.Select(attrs={'class': 'form-control'}, choices=[('', 'Unknown'), (True, 'Yes'), (False, 'No')]),
            'gestational_diabetes_history': forms.Select(attrs={'class': 'form-control'}, choices=[('', 'Unknown'), (True, 'Yes'), (False, 'No')]),
            'pcos_history': forms.Select(attrs={'class': 'form-control'}, choices=[('', 'Unknown'), (True, 'Yes'), (False, 'No')]),
            'dietary_habits': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'eating_habits': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'nutrition_assessment': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'food_allergies_or_intolerance': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'food_affordability_and_preparation': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'food_preference_and_culture': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'physical_activity_level': forms.Select(attrs={'class': 'form-control'}),
            'lifestyle_factors': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'sleep_quality': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'stress_level': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'alcohol_intake': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'smoking_status': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'work_schedule': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'laboratory_results_summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'readiness_to_change': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['assessed_at'].initial = timezone.localtime().strftime('%Y-%m-%dT%H:%M')

    def clean_assessed_at(self):
        assessed_at = self.cleaned_data['assessed_at']
        if timezone.is_naive(assessed_at):
            return timezone.make_aware(assessed_at, timezone.get_current_timezone())
        return assessed_at


class SignUpForm(UserCreationForm):
    role = forms.ChoiceField(
        required=True,
        choices=UserProfile.ROLE_CHOICES,
        initial=UserProfile.ROLE_PATIENT,
        label='Sign up as',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    agree_to_terms = forms.BooleanField(
        required=True,
        label='I agree to the Terms of Use and Privacy Notice',
        error_messages={'required': 'You must agree to the Terms of Use and Privacy Notice to register.'}
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
