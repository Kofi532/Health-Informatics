from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import BlogPost, Comment, Patient, UserProfile, PatientProfile, GlucoseLog, LabResult, DiabetesAssessment, DiabetesDiagnosisSummary
from .views import get_patient_for_user


class BlogResearchDataTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='patient1', password='secret123')
        self.patient = Patient.objects.create(
            first_name='Ada',
            last_name='Lovelace',
            date_of_birth='1990-01-01',
            gender='F',
        )
        UserProfile.objects.create(user=self.user, patient=self.patient)

    def test_get_patient_for_user_creates_and_links_a_patient_when_missing(self):
        user = get_user_model().objects.create_user(username='newpatient', password='secret123')

        patient = get_patient_for_user(user)

        self.assertIsNotNone(patient)
        self.assertEqual(patient.first_name, 'newpatient')
        self.assertTrue(UserProfile.objects.filter(user=user, patient=patient).exists())

    def test_patient_blog_post_and_comment_are_linked_to_research_data(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('patients:blog_list'), {
            'feeling': 'I felt tired today.',
            'category': BlogPost.CATEGORY_PHYSICIAN,
        })
        self.assertEqual(response.status_code, 302)

        post = BlogPost.objects.get(title='Feeling update from patient1')
        self.assertEqual(post.patient, self.patient)
        self.assertEqual(post.category, BlogPost.CATEGORY_PHYSICIAN)

        response = self.client.post(
            reverse('patients:blog_detail', args=[post.pk]),
            {'content': 'This is a helpful comment.'},
        )
        self.assertEqual(response.status_code, 302)

        comment = Comment.objects.get(content='This is a helpful comment.')
        self.assertEqual(comment.patient, self.patient)

        response = self.client.post(reverse('patients:lab_result_entry'), {
            'test_name': 'HbA1c',
            'result_value': '6.2',
            'unit': '%',
            'reference_range': '4.0 - 5.6',
            'collected_at': '2026-07-07T09:30',
            'notes': 'Borderline elevated.',
        })
        self.assertEqual(response.status_code, 302)

        lab_result = LabResult.objects.get(test_name='HbA1c')
        self.assertEqual(lab_result.patient, self.patient)

        researcher_response = self.client.get(reverse('patients:researcher_patient_detail', args=[self.patient.pk]))
        self.assertEqual(researcher_response.status_code, 200)
        self.assertContains(researcher_response, 'I felt tired today.')
        self.assertContains(researcher_response, 'This is a helpful comment.')
        self.assertContains(researcher_response, 'Chat with a Physician')
        self.assertContains(researcher_response, 'HbA1c')
        self.assertContains(researcher_response, '6.2')

        list_response = self.client.get(reverse('patients:researcher_patient_list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, 'I felt tired today.')
        self.assertContains(list_response, 'This is a helpful comment.')
        self.assertContains(list_response, 'Chat with a Physician')
        self.assertContains(list_response, 'HbA1c')

    def test_diabetes_assessment_is_visible_to_researcher(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('patients:diabetes_assessment_entry'), {
            'assessment_type': DiabetesAssessment.TYPE_PREDIABETES,
            'diabetes_type': '',
            'fasting_glucose': '108.0',
            'post_meal_glucose': '146.0',
            'hba1c': '5.9',
            'insulin_use': '',
            'oral_medication_use': 'False',
            'medication_timing': 'Medication taken after breakfast.',
            'current_medications': 'Metformin 500mg daily.',
            'weight_kg': '76.5',
            'height_cm': '172.0',
            'bmi': '25.9',
            'waist_circumference_cm': '95.0',
            'medical_history': 'Mild hypertension and elevated cholesterol.',
            'family_history_diabetes': 'True',
            'high_bp_history': 'True',
            'high_cholesterol_history': 'True',
            'gestational_diabetes_history': '',
            'pcos_history': '',
            'dietary_habits': 'Frequent refined carbohydrate meals and snacks.',
            'eating_habits': 'Low vegetables, frequent sugary drinks.',
            'nutrition_assessment': 'Portion size large, low fiber intake, low water intake.',
            'food_allergies_or_intolerance': 'None reported.',
            'food_affordability_and_preparation': 'Can prepare meals on weekends only.',
            'food_preference_and_culture': 'Prefers traditional high-carb meals.',
            'physical_activity_level': DiabetesAssessment.ACTIVITY_LOW,
            'lifestyle_factors': 'Poor sleep and high job stress.',
            'sleep_quality': '5 hours on workdays.',
            'stress_level': 'High',
            'alcohol_intake': 'Occasional',
            'smoking_status': 'Non-smoker',
            'work_schedule': 'Shift-based',
            'occupation': 'Office administrator',
            'laboratory_results_summary': 'LDL elevated, kidney function normal.',
            'readiness_to_change': DiabetesAssessment.READINESS_MEDIUM,
            'assessed_at': '2026-07-07T10:30',
        })

        self.assertEqual(response.status_code, 302)
        assessment = DiabetesAssessment.objects.get(patient=self.patient)
        self.assertEqual(assessment.assessment_type, DiabetesAssessment.TYPE_PREDIABETES)
        self.assertEqual(str(assessment.fasting_glucose), '108.00')

        researcher_response = self.client.get(reverse('patients:researcher_patient_detail', args=[self.patient.pk]))
        self.assertEqual(researcher_response.status_code, 200)
        self.assertContains(researcher_response, 'Patient with Prediabetes')
        self.assertContains(researcher_response, 'HbA1c')

        list_response = self.client.get(reverse('patients:researcher_patient_list'))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, 'Patient with Prediabetes')

    def test_diagnosis_summary_computes_diabetes_for_hba1c_threshold(self):
        self.client.force_login(self.user)

        self.client.post(reverse('patients:diabetes_assessment_entry'), {
            'assessment_type': DiabetesAssessment.TYPE_DIABETES,
            'diabetes_type': DiabetesAssessment.DIABETES_TYPE_2,
            'fasting_glucose': '',
            'post_meal_glucose': '',
            'hba1c': '',
            'classic_hyperglycemia_symptoms': '',
            'insulin_use': '',
            'oral_medication_use': '',
            'medication_timing': '',
            'current_medications': '',
            'weight_kg': '',
            'height_cm': '',
            'bmi': '',
            'waist_circumference_cm': '',
            'medical_history': '',
            'family_history_diabetes': '',
            'high_bp_history': '',
            'high_cholesterol_history': '',
            'gestational_diabetes_history': '',
            'pcos_history': '',
            'dietary_habits': '',
            'eating_habits': '',
            'nutrition_assessment': '',
            'food_allergies_or_intolerance': '',
            'food_affordability_and_preparation': '',
            'food_preference_and_culture': '',
            'physical_activity_level': '',
            'lifestyle_factors': '',
            'sleep_quality': '',
            'stress_level': '',
            'alcohol_intake': '',
            'smoking_status': '',
            'work_schedule': '',
            'occupation': '',
            'laboratory_results_summary': '',
            'readiness_to_change': '',
            'assessed_at': '2026-07-07T10:30',
        })

        self.client.post(reverse('patients:lab_result_entry'), {
            'test_name': 'HbA1c',
            'result_value': '6.6',
            'unit': '%',
            'reference_range': '4.0 - 5.6',
            'collected_at': '2026-07-07T11:00',
            'notes': '',
        })

        summary = DiabetesDiagnosisSummary.objects.get(patient=self.patient)
        self.assertEqual(summary.status, DiabetesDiagnosisSummary.STATUS_DIABETES)
        self.assertEqual(summary.confirmation_status, DiabetesDiagnosisSummary.PROVISIONAL)

    def test_lab_result_entry_saves_recent_results_for_patient(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse('patients:lab_result_entry'), {
            'test_name': 'Fasting Glucose',
            'result_value': '102',
            'unit': 'mg/dL',
            'reference_range': '70 - 99',
            'collected_at': '2026-07-07T08:00',
            'notes': 'Collected before breakfast.',
        })

        self.assertEqual(response.status_code, 302)
        lab_result = LabResult.objects.get(test_name='Fasting Glucose')
        self.assertEqual(lab_result.patient, self.patient)
        self.assertEqual(lab_result.unit, 'mg/dL')

    def test_blog_list_filters_posts_by_selected_sub_blog(self):
        self.client.force_login(self.user)

        self.client.post(reverse('patients:blog_list'), {
            'feeling': 'I need meal planning support.',
            'category': BlogPost.CATEGORY_DIETICIAN,
        })
        self.client.post(reverse('patients:blog_list'), {
            'feeling': 'This is a general health update.',
            'category': BlogPost.CATEGORY_GENERAL,
        })

        response = self.client.get(reverse('patients:blog_list'), {'category': BlogPost.CATEGORY_DIETICIAN})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'I need meal planning support.')
        self.assertNotContains(response, 'This is a general health update.')
        self.assertEqual(response.context['active_category'], BlogPost.CATEGORY_DIETICIAN)

    def test_signup_redirects_to_dashboard_and_creates_profile(self):
        response = self.client.post(reverse('patients:signup'), {
            'username': 'newpatient',
            'email': 'newpatient@example.com',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
            'agree_to_terms': 'on',
        })

        self.assertEqual(response.status_code, 302)
        self.assertTrue(get_user_model().objects.filter(username='newpatient').exists())
        user = get_user_model().objects.get(username='newpatient')
        self.assertTrue(PatientProfile.objects.filter(user=user).exists())
        self.assertEqual(response.url, reverse('patients:patient_dashboard'))
