from datetime import datetime, timedelta
from decimal import Decimal
import random

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from patients.models import DiabetesAssessment, GlucoseLog, Patient, PatientProfile, UserProfile


class Command(BaseCommand):
    help = 'Populate a balanced demo cohort for the researcher statistical tests page.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--replace',
            action='store_true',
            help='Delete previously generated stats demo cohort before recreating it.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(20260723)
        prefix = 'stats_demo_'

        if options['replace']:
            self._clear_existing(prefix)

        researcher_group, _ = Group.objects.get_or_create(name='Biostatistician')
        researcher_user, created = User.objects.get_or_create(
            username='researcher_stats_demo',
            defaults={
                'first_name': 'Stats',
                'last_name': 'Researcher',
                'email': 'researcher.stats.demo@example.com',
                'is_active': True,
            },
        )
        if created:
            researcher_user.set_password('demo12345')
            researcher_user.save(update_fields=['password'])
        researcher_user.groups.add(researcher_group)
        UserProfile.objects.get_or_create(
            user=researcher_user,
            defaults={'role': UserProfile.ROLE_RESEARCHER},
        )

        first_names = [
            'Ama', 'Kojo', 'Akosua', 'Yaw', 'Abena', 'Kofi', 'Esi', 'Kwesi', 'Efua', 'Kwaku',
            'Akua', 'Kwabena', 'Adwoa', 'Nana', 'Afia', 'Kojoa', 'Yaa', 'Mawuli', 'Selorm', 'Dzifa',
            'Afi', 'Nii', 'Ato', 'Mansa', 'Naana', 'Korkor', 'Zanetor', 'Akwele', 'Farida', 'Mariam',
            'Rahim', 'Sule', 'Bawa', 'Nabila', 'Fati', 'Hawa',
        ]
        last_names = [
            'Mensah', 'Boateng', 'Owusu', 'Asare', 'Agyeman', 'Asante', 'Appiah', 'Sarpong', 'Tetteh',
            'Nkrumah', 'Ayisi', 'Opoku', 'Kusi', 'Darko', 'Quaye', 'Ababio', 'Lamptey', 'Koomson',
        ]
        regions = [
            'Greater Accra', 'Ashanti', 'Northern', 'Eastern', 'Volta', 'Central',
        ]
        occupations = [
            'Trader', 'Teacher', 'Banker', 'Nurse', 'Farmer', 'Designer', 'Driver', 'Engineer',
        ]
        diet_notes = [
            'Balanced meals with moderate starch portions.',
            'Late-night snacking and sugary drinks reported.',
            'Vegetable-forward diet with consistent hydration.',
            'Irregular meals due to shift work and transport constraints.',
        ]

        type_profiles = {
            DiabetesAssessment.DIABETES_TYPE_1: {
                'base_glucose': 148,
                'variability': 18,
                'assessment_type': DiabetesAssessment.TYPE_DIABETES,
                'waist': 80,
                'bmi': 24,
            },
            DiabetesAssessment.DIABETES_TYPE_2: {
                'base_glucose': 182,
                'variability': 24,
                'assessment_type': DiabetesAssessment.TYPE_DIABETES,
                'waist': 96,
                'bmi': 31,
            },
            DiabetesAssessment.DIABETES_GESTATIONAL: {
                'base_glucose': 136,
                'variability': 14,
                'assessment_type': DiabetesAssessment.TYPE_PREDIABETES,
                'waist': 88,
                'bmi': 28,
            },
        }
        locality_adjustments = {
            'Urban': {'glucose': 8, 'variability': 4, 'activity': DiabetesAssessment.ACTIVITY_LOW},
            'Rural': {'glucose': -4, 'variability': 2, 'activity': DiabetesAssessment.ACTIVITY_MODERATE},
            'Peri-Urban': {'glucose': 2, 'variability': 3, 'activity': DiabetesAssessment.ACTIVITY_MODERATE},
        }
        meal_contexts = [
            GlucoseLog.FASTING,
            GlucoseLog.ONE_HOUR_BREAKFAST,
            GlucoseLog.TWO_HOUR_BREAKFAST,
            GlucoseLog.ONE_HOUR_LUNCH,
            GlucoseLog.TWO_HOUR_LUNCH,
            GlucoseLog.ONE_HOUR_DINNER,
            GlucoseLog.TWO_HOUR_DINNER,
        ]

        cohort_specs = []
        patient_index = 0
        for diabetes_type in [
            DiabetesAssessment.DIABETES_TYPE_1,
            DiabetesAssessment.DIABETES_TYPE_2,
            DiabetesAssessment.DIABETES_GESTATIONAL,
        ]:
            for gender in ['F', 'M']:
                if diabetes_type == DiabetesAssessment.DIABETES_GESTATIONAL and gender != 'F':
                    continue
                for locality in ['Urban', 'Rural', 'Peri-Urban']:
                    for risk_band in ['low', 'moderate', 'high']:
                        if diabetes_type == DiabetesAssessment.DIABETES_GESTATIONAL and risk_band == 'high' and locality == 'Rural':
                            continue
                        cohort_specs.append({
                            'index': patient_index,
                            'diabetes_type': diabetes_type,
                            'gender': gender,
                            'locality': locality,
                            'risk_band': risk_band,
                        })
                        patient_index += 1

        created_patients = 0
        created_logs = 0
        created_assessments = 0

        for spec in cohort_specs:
            username = f"{prefix}{spec['index']:02d}"
            if User.objects.filter(username=username).exists():
                continue

            first_name = first_names[spec['index'] % len(first_names)]
            last_name = last_names[(spec['index'] * 2) % len(last_names)]
            region = regions[spec['index'] % len(regions)]
            occupation = occupations[spec['index'] % len(occupations)]
            type_profile = type_profiles[spec['diabetes_type']]
            locality_profile = locality_adjustments[spec['locality']]
            age_years = 22 + (spec['index'] % 21)
            if spec['risk_band'] == 'high':
                age_years += 11
            elif spec['risk_band'] == 'moderate':
                age_years += 5
            age_years = min(age_years, 54)

            today = timezone.now().date()
            dob = today - timedelta(days=365 * age_years + rng.randint(0, 364))
            risk_shift = {'low': -18, 'moderate': 3, 'high': 28}[spec['risk_band']]
            variability_shift = {'low': -7, 'moderate': 0, 'high': 12}[spec['risk_band']]
            glucose_center = type_profile['base_glucose'] + locality_profile['glucose'] + risk_shift
            glucose_spread = max(8, type_profile['variability'] + locality_profile['variability'] + variability_shift)
            hba1c = round((glucose_center + 46.7) / 28.7 + rng.uniform(-0.35, 0.35), 2)
            fasting_glucose = round(glucose_center - rng.uniform(8, 16), 2)
            post_meal_glucose = round(glucose_center + rng.uniform(10, 24), 2)
            bmi = round(type_profile['bmi'] + rng.uniform(-2.3, 2.6) + (0.8 if spec['risk_band'] == 'high' else 0), 2)
            height_cm = round(rng.uniform(156, 180), 2)
            weight_kg = round(bmi * ((height_cm / 100) ** 2), 2)
            waist_cm = round(type_profile['waist'] + rng.uniform(-5, 8) + (4 if spec['risk_band'] == 'high' else 0), 2)
            readiness = {
                'low': DiabetesAssessment.READINESS_HIGH,
                'moderate': DiabetesAssessment.READINESS_MEDIUM,
                'high': DiabetesAssessment.READINESS_LOW,
            }[spec['risk_band']]

            user = User.objects.create_user(
                username=username,
                password='demo12345',
                first_name=first_name,
                last_name=last_name,
                email=f'{username}@example.com',
            )
            patient = Patient.objects.create(
                first_name=first_name,
                last_name=last_name,
                date_of_birth=dob,
                gender=spec['gender'],
                email=user.email,
                phone_number=f'020{spec["index"]:07d}'[:20],
                address=f'{spec["locality"]} district, {region}',
                region=region,
                locality_type=spec['locality'],
                emergency_contact='Demo contact',
            )
            UserProfile.objects.create(user=user, patient=patient, role=UserProfile.ROLE_PATIENT)
            profile = PatientProfile.objects.create(
                user=user,
                gestational_age_weeks=28 + (spec['index'] % 9),
                target_fasting_glucose=95 if spec['diabetes_type'] != DiabetesAssessment.DIABETES_TYPE_2 else 100,
                doctor_email='stats.demo.clinician@example.com',
                allow_all_physicians=True,
                allow_all_dieticians=True,
            )

            assessed_at = timezone.make_aware(datetime.combine(today - timedelta(days=4 + spec['index'] % 17), datetime.min.time()))
            DiabetesAssessment.objects.create(
                patient=patient,
                assessment_type=type_profile['assessment_type'],
                diabetes_type=spec['diabetes_type'],
                fasting_glucose=Decimal(str(fasting_glucose)),
                post_meal_glucose=Decimal(str(post_meal_glucose)),
                hba1c=Decimal(str(hba1c)),
                classic_hyperglycemia_symptoms=spec['risk_band'] == 'high',
                insulin_use=spec['diabetes_type'] == DiabetesAssessment.DIABETES_TYPE_1,
                oral_medication_use=spec['diabetes_type'] != DiabetesAssessment.DIABETES_TYPE_1,
                medication_timing='Before breakfast and dinner',
                current_medications='Metformin / insulin demo schedule',
                weight_kg=Decimal(str(weight_kg)),
                height_cm=Decimal(str(height_cm)),
                bmi=Decimal(str(bmi)),
                waist_circumference_cm=Decimal(str(waist_cm)),
                medical_history='Generated demo cohort for researcher analytics.',
                family_history_diabetes=spec['risk_band'] != 'low',
                high_bp_history=spec['risk_band'] == 'high',
                high_cholesterol_history=spec['diabetes_type'] == DiabetesAssessment.DIABETES_TYPE_2,
                gestational_diabetes_history=spec['diabetes_type'] == DiabetesAssessment.DIABETES_GESTATIONAL,
                pcos_history=spec['gender'] == 'F' and spec['risk_band'] == 'moderate',
                dietary_habits=rng.choice(diet_notes),
                eating_habits='Regular meals with variable carbohydrate portions.',
                nutrition_assessment='Demo assessment to support cohort analytics and comparative testing.',
                food_affordability_and_preparation='Moderate access to fresh foods.',
                food_preference_and_culture='Local mixed diet pattern.',
                physical_activity_level=locality_profile['activity'],
                lifestyle_factors='Stress and sleep vary by occupational schedule.',
                sleep_quality='Average',
                stress_level='Moderate' if spec['risk_band'] != 'low' else 'Low',
                alcohol_intake='Occasional',
                smoking_status='Non-smoker',
                work_schedule='Day shift' if spec['locality'] != 'Urban' else 'Variable shift',
                occupation=occupation,
                laboratory_results_summary='HbA1c and glucose values seeded for statistical exploration.',
                readiness_to_change=readiness,
                assessed_at=assessed_at,
            )
            created_assessments += 1

            total_days = 28
            reading_target = 12 + (spec['index'] % 6)
            for reading_index in range(reading_target):
                day_offset = reading_index * max(1, total_days // reading_target)
                meal_context = meal_contexts[reading_index % len(meal_contexts)]
                meal_shift = {
                    GlucoseLog.FASTING: -10,
                    GlucoseLog.ONE_HOUR_BREAKFAST: 14,
                    GlucoseLog.TWO_HOUR_BREAKFAST: 5,
                    GlucoseLog.ONE_HOUR_LUNCH: 12,
                    GlucoseLog.TWO_HOUR_LUNCH: 4,
                    GlucoseLog.ONE_HOUR_DINNER: 10,
                    GlucoseLog.TWO_HOUR_DINNER: 3,
                }[meal_context]
                value = round(rng.gauss(glucose_center + meal_shift, glucose_spread))
                value = max(72, min(278, value))
                timestamp = timezone.now() - timedelta(days=total_days - day_offset, hours=6 + (reading_index % 8))
                GlucoseLog.objects.create(
                    profile=profile,
                    timestamp=timestamp,
                    glucose_level=value,
                    meal_context=meal_context,
                )
                created_logs += 1

            created_patients += 1

        total_demo_patients = Patient.objects.filter(email__iendswith='@example.com', user_profile__user__username__startswith=prefix).count()
        self.stdout.write(self.style.SUCCESS(
            f'Population complete: created {created_patients} demo patients, {created_assessments} assessments, and {created_logs} glucose logs. Demo cohort size is now {total_demo_patients}.'
        ))
        self.stdout.write('Research demo login: researcher_stats_demo / demo12345')

    def _clear_existing(self, prefix):
        users = list(User.objects.filter(username__startswith=prefix))
        patient_ids = list(
            UserProfile.objects.filter(user__in=users, patient__isnull=False).values_list('patient_id', flat=True)
        )
        if patient_ids:
            GlucoseLog.objects.filter(profile__user__in=users).delete()
            DiabetesAssessment.objects.filter(patient_id__in=patient_ids).delete()
            PatientProfile.objects.filter(user__in=users).delete()
            UserProfile.objects.filter(user__in=users).delete()
            Patient.objects.filter(id__in=patient_ids).delete()
        User.objects.filter(username__startswith=prefix).delete()