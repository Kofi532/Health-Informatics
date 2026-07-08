from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from .forms import SignUpForm
from django.contrib.auth import login
from django.contrib.auth.models import Group, User
from django.utils import timezone
from django.contrib import messages
from datetime import timedelta, datetime
from django.utils.text import slugify
from django.http import HttpResponse, HttpResponseForbidden
from django.conf import settings
import csv
import hashlib, hmac
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from .models import Patient, BlogPost, Comment, UserProfile, PatientProfile, GlucoseLog, DoctorAlert, MedicationLog, GlucosePrediction, Prescription, LabResult, DiabetesAssessment
from django.db.models import Q
from .forms import GlucoseLogForm, MedicationChecklistForm, PrescriptionForm, LabResultForm, DiabetesAssessmentForm
from .utils import calculate_linear_regression, compute_patient_glucose_stats, compute_population_stats
from .diagnosis import recompute_patient_diagnosis
import json


def _join_values(values):
    return '; '.join(str(v) for v in values if v)


def _export_cell(value):
    if value is None:
        return 'N/A'
    if isinstance(value, str) and not value.strip():
        return 'N/A'
    return value


def is_physician_user(user):
    if not getattr(user, 'is_authenticated', False):
        return False

    profile = UserProfile.objects.filter(user=user).only('role').first()
    if profile is not None and profile.role == UserProfile.ROLE_PHYSICIAN:
        return True

    return user.groups.filter(name='Clinician').exists()


def get_physician_users_queryset():
    return User.objects.filter(
        Q(userprofile__role=UserProfile.ROLE_PHYSICIAN) | Q(groups__name='Clinician')
    ).distinct().order_by('username')


def get_patients_approved_for_physician(user):
    return Patient.objects.filter(
        Q(user_profile__user__patient_profile__allow_all_physicians=True)
        | Q(user_profile__user__patient_profile__approved_physicians=user)
    ).distinct().order_by('last_name', 'first_name')


def get_post_owner_approved_physician_ids(post):
    if post.patient is None:
        return set()

    owner_profile = UserProfile.objects.filter(patient=post.patient).select_related('user').first()
    if owner_profile is None:
        return set()

    patient_profile = PatientProfile.objects.filter(user=owner_profile.user).first()
    if patient_profile is None:
        return set()

    return set(patient_profile.approved_physicians.values_list('id', flat=True))


def post_owner_allows_all_physicians(post):
    if post.patient is None:
        return False

    owner_profile = UserProfile.objects.filter(patient=post.patient).select_related('user').first()
    if owner_profile is None:
        return False

    patient_profile = PatientProfile.objects.filter(user=owner_profile.user).only('allow_all_physicians').first()
    if patient_profile is None:
        return False

    return bool(patient_profile.allow_all_physicians)


def get_patient_for_user(user):
    if not getattr(user, 'is_authenticated', False):
        return None

    user_profile = UserProfile.objects.filter(user=user).select_related('patient').first()
    if user_profile is not None and user_profile.patient is not None:
        return user_profile.patient

    if user_profile is None:
        user_profile = UserProfile.objects.create(user=user)

    if user_profile.patient is None:
        patient = Patient.objects.create(
            first_name=user.get_full_name().split()[0] if user.get_full_name() else user.username,
            last_name=' '.join(user.get_full_name().split()[1:]) if user.get_full_name() else 'User',
            date_of_birth='2000-01-01',
            gender='O',
            email=user.email or '',
        )
        user_profile.patient = patient
        user_profile.save(update_fields=['patient'])
        return patient

    return user_profile.patient


@login_required
def patient_list(request):
    if request.method == 'POST':
        feeling_text = request.POST.get('feeling', '').strip()
        if feeling_text:
            title = f"Feeling update from {request.user.get_username()}"
            slug_base = slugify(title)
            slug = slug_base
            count = 1
            while BlogPost.objects.filter(slug=slug).exists():
                count += 1
                slug = f"{slug_base}-{count}"
            patient = get_patient_for_user(request.user)
            BlogPost.objects.create(
                patient=patient,
                title=title,
                slug=slug,
                body=feeling_text,
                published=True,
                published_at=timezone.now(),
            )
            return redirect('patients:blog_list')
    patients = Patient.objects.all().order_by('last_name', 'first_name')
    return render(request, 'patients/patient_list.html', {'patients': patients})


@login_required
def patient_detail(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    return render(request, 'patients/patient_detail.html', {'patient': patient})


@login_required
def researcher_patient_list(request):
    if is_physician_user(request.user):
        patients = get_patients_approved_for_physician(request.user)
    else:
        patients = Patient.objects.all().order_by('last_name', 'first_name')

    patient_content = []
    for patient in patients:
        blog_posts = list(patient.blog_posts.filter(published=True).order_by('-published_at')[:3])
        comments = list(patient.comments.select_related('post').order_by('-created_at')[:3])
        prescriptions = list(patient.prescriptions.order_by('-created_at')[:3])
        lab_results = list(patient.lab_results.order_by('-collected_at')[:3])
        assessments = list(patient.diabetes_assessments.order_by('-assessed_at')[:2])
        diagnosis_summary = getattr(patient, 'diagnosis_summary', None)
        patient_content.append({
            'patient': patient,
            'blog_posts': blog_posts,
            'comments': comments,
            'prescriptions': prescriptions,
            'lab_results': lab_results,
            'assessments': assessments,
            'diagnosis_summary': diagnosis_summary,
        })
    return render(request, 'patients/researcher_patient_list.html', {'patient_content': patient_content})


@login_required
def researcher_patient_detail(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
    if is_physician_user(request.user):
        allowed_patients = get_patients_approved_for_physician(request.user)
        if not allowed_patients.filter(pk=patient.pk).exists():
            return HttpResponseForbidden('You can only view research data for your approved patients.')

    try:
        user_profile = patient.user_profile
    except Exception:
        user_profile = None

    patient_profile = None
    glucose_logs = []
    predictions = []
    alerts = []
    medications = []
    vital_signs = []

    blog_posts = []
    comments = []
    prescriptions = []
    lab_results = []
    assessments = []
    diagnosis_summary = getattr(patient, 'diagnosis_summary', None)

    if user_profile is not None:
        patient_profile = getattr(user_profile.user, 'patient_profile', None)
        if patient_profile is not None:
            glucose_logs = list(patient_profile.glucose_logs.all()[:15])
            predictions = list(patient_profile.predictions.all()[:10])
            alerts = list(patient_profile.doctor_alerts.all()[:10])
            medications = list(patient_profile.medications.all()[:10])

        blog_posts = list(BlogPost.objects.filter(patient=patient, published=True).order_by('-published_at')[:10])
        comments = list(Comment.objects.filter(patient=patient).select_related('post').order_by('-created_at')[:10])
        prescriptions = list(Prescription.objects.filter(patient=patient).order_by('-created_at')[:10])

    lab_results = list(LabResult.objects.filter(patient=patient).order_by('-collected_at')[:10])
    assessments = list(DiabetesAssessment.objects.filter(patient=patient).order_by('-assessed_at')[:10])

    for encounter in patient.encounters.all():
        vital_signs.extend(list(encounter.vital_signs.all()))

    recent_logs = [log for log in glucose_logs if log.timestamp >= timezone.now() - timedelta(days=7)]
    average_glucose = None
    if recent_logs:
        average_glucose = round(sum(log.glucose_level for log in recent_logs) / len(recent_logs), 1)

    return render(request, 'patients/researcher_patient_detail.html', {
        'patient': patient,
        'user_profile': user_profile,
        'patient_profile': patient_profile,
        'glucose_logs': glucose_logs,
        'predictions': predictions,
        'alerts': alerts,
        'medications': medications,
        'vital_signs': vital_signs,
        'average_glucose': average_glucose,
        'blog_posts': blog_posts,
        'comments': comments,
        'prescriptions': prescriptions,
        'lab_results': lab_results,
        'assessments': assessments,
        'diagnosis_summary': diagnosis_summary,
    })


@login_required
def blog_list(request):
    physician_user = is_physician_user(request.user)
    search_query = request.GET.get('q', '').strip()
    selected_patient_filter = request.GET.get('approved_patient', '').strip()
    category_choices = list(BlogPost.CATEGORY_CHOICES)
    valid_categories = {value for value, _label in category_choices}
    category_labels = dict(category_choices)
    active_category = request.GET.get('category', BlogPost.CATEGORY_GENERAL)
    if active_category not in valid_categories:
        active_category = BlogPost.CATEGORY_GENERAL

    if physician_user:
        # Physicians use the dedicated physician chat stream only.
        active_category = BlogPost.CATEGORY_PHYSICIAN

    if request.method == 'POST':
        if physician_user:
            messages.error(request, 'Physicians can comment on patient posts but cannot create new blog posts.')
            return redirect(f"{request.path}?category={active_category}")

        feeling_text = request.POST.get('feeling', '').strip()
        category = request.POST.get('category', active_category)
        if category not in valid_categories:
            category = BlogPost.CATEGORY_GENERAL
        if feeling_text:
            title = f"Feeling update from {request.user.get_username()}"
            slug_base = slugify(title)
            slug = slug_base
            count = 1
            while BlogPost.objects.filter(slug=slug).exists():
                count += 1
                slug = f"{slug_base}-{count}"
            patient = get_patient_for_user(request.user)
            BlogPost.objects.create(
                patient=patient,
                category=category,
                title=title,
                slug=slug,
                body=feeling_text,
                published=True,
                published_at=timezone.now(),
            )
            return redirect(f"{request.path}?category={category}")

    posts = BlogPost.objects.filter(published=True, category=active_category)
    approved_patients = []
    physician_dialogues = []

    if physician_user:
        approved_patients = list(get_patients_approved_for_physician(request.user))

        if selected_patient_filter:
            try:
                selected_patient_id = int(selected_patient_filter)
                approved_patients = [patient for patient in approved_patients if patient.id == selected_patient_id]
            except ValueError:
                selected_patient_filter = ''

        if search_query:
            query_lower = search_query.lower()
            filtered_patients = []
            for patient in approved_patients:
                owner_profile = UserProfile.objects.filter(patient=patient).select_related('user').first()
                patient_username = owner_profile.user.username if owner_profile is not None else ''
                full_name = f"{patient.first_name} {patient.last_name}".strip()
                if query_lower in patient_username.lower() or query_lower in full_name.lower():
                    filtered_patients.append(patient)
            approved_patients = filtered_patients

        posts = posts.filter(patient__in=approved_patients)
        physician_patient = get_patient_for_user(request.user)

        for patient in approved_patients:
            owner_profile = UserProfile.objects.filter(patient=patient).select_related('user').first()
            patient_username = owner_profile.user.username if owner_profile is not None else 'unknown'
            patient_posts = posts.filter(patient=patient)
            latest_post = patient_posts.order_by('-published_at').first()

            latest_comment = Comment.objects.filter(post__in=patient_posts).order_by('-created_at').first()
            latest_message_preview = ''
            last_message_at = None
            if latest_comment is not None and (latest_post is None or latest_comment.created_at >= latest_post.published_at):
                latest_message_preview = latest_comment.content
                last_message_at = latest_comment.created_at
            elif latest_post is not None:
                latest_message_preview = latest_post.body
                last_message_at = latest_post.published_at

            unread_qs = Comment.objects.filter(post__in=patient_posts)
            if physician_patient is not None:
                unread_count = unread_qs.exclude(patient=physician_patient).count()
            else:
                unread_count = unread_qs.count()

            physician_dialogues.append({
                'patient': patient,
                'patient_username': patient_username,
                'latest_post': latest_post,
                'last_message_preview': latest_message_preview,
                'last_message_at': last_message_at,
                'unread_count': unread_count,
            })

        physician_dialogues.sort(
            key=lambda item: item['last_message_at'] or timezone.make_aware(datetime.min),
            reverse=True,
        )

    return render(request, 'patients/blog_list.html', {
        'posts': posts,
        'active_category': active_category,
        'active_category_label': category_labels[active_category],
        'physician_user': physician_user,
        'physician_dialogues': physician_dialogues,
        'approved_patients': approved_patients,
        'search_query': search_query,
        'selected_patient_filter': selected_patient_filter,
        'blog_categories': [
            {'value': value, 'label': label}
            for value, label in category_choices
        ],
    })


@login_required
def blog_detail(request, pk):
    post = get_object_or_404(BlogPost, pk=pk, published=True)
    physician_user = is_physician_user(request.user)
    valid_categories = {value for value, _label in BlogPost.CATEGORY_CHOICES}
    category = request.GET.get('category', post.category)
    if category not in valid_categories:
        category = post.category

    if physician_user:
        if post.category != BlogPost.CATEGORY_PHYSICIAN:
            return HttpResponseForbidden('Physicians can only access Chat with a Physician posts.')

        approved_patients = get_patients_approved_for_physician(request.user)
        if not approved_patients.filter(pk=getattr(post.patient, 'pk', None)).exists():
            return HttpResponseForbidden('You can only access chats for your approved patients.')

    physician_only_comments = post.category == BlogPost.CATEGORY_PHYSICIAN
    can_comment = request.user.is_authenticated
    comment_restriction_message = ''

    if is_physician_user(request.user) and post.category != BlogPost.CATEGORY_PHYSICIAN:
        can_comment = False
        comment_restriction_message = 'Physicians can only comment on posts in Chat with a Physician.'
    elif physician_only_comments:
        if not is_physician_user(request.user):
            can_comment = False
            comment_restriction_message = 'Only physicians can comment in the Chat with a Physician area.'
        else:
            all_physicians_allowed = post_owner_allows_all_physicians(post)
            if not all_physicians_allowed:
                approved_ids = get_post_owner_approved_physician_ids(post)
                if request.user.id not in approved_ids:
                    can_comment = False
                    comment_restriction_message = 'Only physicians approved by this patient can comment in the Chat with a Physician area.'

    if request.method == 'POST':
        if not can_comment:
            messages.error(request, comment_restriction_message or 'You are not allowed to comment on this post.')
            return redirect(f"{post.get_absolute_url()}?category={category}")

        content = request.POST.get('content', '').strip()
        if content:
            author_name = request.user.get_full_name() or request.user.get_username()
            patient = get_patient_for_user(request.user)
            Comment.objects.create(post=post, patient=patient, author_name=author_name, content=content)
            return redirect(f"{post.get_absolute_url()}?category={category}")
    comments = post.comments.all()
    return render(request, 'patients/blog_detail.html', {
        'post': post,
        'comments': comments,
        'active_category': category,
        'can_comment': can_comment,
        'comment_restriction_message': comment_restriction_message,
    })


@login_required
def prescription_entry(request):
    if not is_physician_user(request.user):
        return HttpResponseForbidden('Only physicians can add prescriptions.')

    approved_patients = list(get_patients_approved_for_physician(request.user))
    selected_patient = None

    selected_patient_id = request.GET.get('patient_id', '').strip()
    if request.method == 'POST':
        selected_patient_id = request.POST.get('patient_id', '').strip() or selected_patient_id

    if selected_patient_id:
        try:
            selected_patient = next(
                patient for patient in approved_patients if patient.id == int(selected_patient_id)
            )
        except (ValueError, StopIteration):
            selected_patient = None

    if selected_patient is None and approved_patients:
        selected_patient = approved_patients[0]

    if request.method == 'POST':
        form = PrescriptionForm(request.POST)
        if form.is_valid():
            if selected_patient is None:
                messages.error(request, 'Select an approved patient before adding a prescription.')
                return render(request, 'patients/prescription_form.html', {
                    'form': form,
                    'prescriptions': [],
                    'approved_patients': approved_patients,
                    'selected_patient': None,
                })

            prescription = form.save(commit=False)
            prescription.patient = selected_patient
            prescription.save()
            messages.success(request, 'Prescription saved successfully.')
            return redirect(f"{request.path}?patient_id={selected_patient.id}")
        else:
            messages.error(request, 'Please complete the prescription form correctly.')
    else:
        form = PrescriptionForm()

    prescriptions = []
    if selected_patient is not None:
        prescriptions = list(Prescription.objects.filter(patient=selected_patient).order_by('-created_at')[:10])

    return render(request, 'patients/prescription_form.html', {
        'form': form,
        'prescriptions': prescriptions,
        'approved_patients': approved_patients,
        'selected_patient': selected_patient,
    })


@login_required
def lab_result_entry(request):
    patient = get_patient_for_user(request.user)
    if request.method == 'POST':
        form = LabResultForm(request.POST)
        if form.is_valid():
            if patient is None:
                patient_profile = UserProfile.objects.filter(user=request.user).first()
                if patient_profile is not None:
                    patient = patient_profile.patient
            if patient is None:
                messages.error(request, 'No patient profile is linked to your account yet. Please contact support.')
                return render(request, 'patients/lab_result_form.html', {'form': form, 'lab_results': []})

            lab_result = form.save(commit=False)
            lab_result.patient = patient
            lab_result.save()
            recompute_patient_diagnosis(patient)
            messages.success(request, 'Lab result saved successfully.')
            return redirect('patients:lab_result_entry')
        messages.error(request, 'Please complete the lab form correctly.')
    else:
        form = LabResultForm()

    lab_results = []
    if patient is not None:
        lab_results = list(LabResult.objects.filter(patient=patient).order_by('-collected_at')[:10])

    return render(request, 'patients/lab_result_form.html', {
        'form': form,
        'lab_results': lab_results,
    })


@login_required
def diabetes_assessment_entry(request):
    patient = get_patient_for_user(request.user)
    if request.method == 'POST':
        form = DiabetesAssessmentForm(request.POST)
        if form.is_valid():
            if patient is None:
                patient_profile = UserProfile.objects.filter(user=request.user).first()
                if patient_profile is not None:
                    patient = patient_profile.patient
            if patient is None:
                messages.error(request, 'No patient profile is linked to your account yet. Please contact support.')
                return render(request, 'patients/diabetes_assessment_form.html', {'form': form, 'assessments': []})

            assessment = form.save(commit=False)
            assessment.patient = patient
            assessment.save()
            recompute_patient_diagnosis(patient)
            messages.success(request, 'Assessment saved successfully.')
            return redirect('patients:diabetes_assessment_entry')
        messages.error(request, 'Please complete the assessment form correctly.')
    else:
        form = DiabetesAssessmentForm()

    assessments = []
    if patient is not None:
        assessments = list(DiabetesAssessment.objects.filter(patient=patient).order_by('-assessed_at')[:10])

    return render(request, 'patients/diabetes_assessment_form.html', {
        'form': form,
        'assessments': assessments,
    })


def signup(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            selected_role = form.cleaned_data.get('role', UserProfile.ROLE_PATIENT)

            user_profile, _ = UserProfile.objects.get_or_create(user=user)
            user_profile.role = selected_role
            user_profile.save(update_fields=['role'])

            role_to_group = {
                UserProfile.ROLE_PATIENT: 'Patient',
                UserProfile.ROLE_PHYSICIAN: 'Clinician',
                UserProfile.ROLE_DIETICIAN: 'Dietician',
                UserProfile.ROLE_RESEARCHER: 'Biostatistician',
            }
            group_name = role_to_group.get(selected_role)
            if group_name:
                group, _ = Group.objects.get_or_create(name=group_name)
                user.groups.clear()
                user.groups.add(group)

            if selected_role == UserProfile.ROLE_PATIENT:
                PatientProfile.objects.get_or_create(user=user, defaults={'gestational_age_weeks': 0})

            login(request, user)

            role_landing = {
                UserProfile.ROLE_PATIENT: 'patients:patient_dashboard',
                UserProfile.ROLE_PHYSICIAN: 'patients:doctor_dashboard',
                UserProfile.ROLE_DIETICIAN: 'patients:blog_list',
                UserProfile.ROLE_RESEARCHER: 'patients:researcher_patient_list',
            }
            return redirect(role_landing.get(selected_role, 'patients:patient_dashboard'))
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})


@login_required
def glucose_log_entry(request):
    # ensure the user has a PatientProfile so they can log readings
    profile, _ = PatientProfile.objects.get_or_create(user=request.user, defaults={'gestational_age_weeks': 0})

    if request.method == 'POST':
        form = GlucoseLogForm(request.POST)
        if form.is_valid():
            glucose_log = form.save(commit=False)
            glucose_log.profile = profile
            glucose_log.save()
            # After saving, pull the last 7 days of readings and compute mean/std
            seven_days_ago = timezone.now() - timedelta(days=7)
            recent_qs = GlucoseLog.objects.filter(profile=profile, timestamp__gte=seven_days_ago)
            levels = list(recent_qs.values_list('glucose_level', flat=True))

            mean, std = compute_population_stats(levels)

            # Determine if new reading is a spike
            is_spike = False
            new_val = glucose_log.glucose_level
            if mean is not None and std is not None and std > 0:
                if new_val > mean + 2 * std:
                    is_spike = True

            # Clinical post-prandial threshold
            if glucose_log.meal_context != GlucoseLog.FASTING and new_val >= 140:
                is_spike = True

            if is_spike:
                messages.warning(request, 'Spike detected: your recent reading appears elevated. Contact your care team if needed.')
                # Create a doctor alert for this spike
                alert_type = DoctorAlert.SPIKE if glucose_log.meal_context != GlucoseLog.FASTING and new_val >= 140 else DoctorAlert.ANOMALY
                alert_message = f"Patient {request.user.username} logged {new_val} mg/dL at {glucose_log.get_meal_context_display()}"
                DoctorAlert.objects.create(
                    patient_profile=profile,
                    glucose_log=glucose_log,
                    alert_type=alert_type,
                    message=alert_message,
                )

            # generate and save a short-term prediction asynchronously if possible
            try:
                from .prediction import generate_and_save_prediction
                try:
                    generate_and_save_prediction(profile)
                except Exception:
                    # do not block user flow on prediction errors
                    pass
            except Exception:
                pass

            return redirect('patients:patient_dashboard')
    else:
        form = GlucoseLogForm()

    return render(request, 'patients/glucose_log_form.html', {'form': form})


@login_required
def patient_dashboard(request):
    form = GlucoseLogForm()
    # ensure profile exists
    profile, _ = PatientProfile.objects.get_or_create(user=request.user, defaults={'gestational_age_weeks': 0})
    physician_users = list(get_physician_users_queryset())
    approved_physicians = list(profile.approved_physicians.order_by('username'))
    approved_physician_ids = {physician.id for physician in approved_physicians}
    available_physicians = [physician for physician in physician_users if physician.id not in approved_physician_ids]
    patient = get_patient_for_user(request.user)
    diagnosis_summary = None
    if patient is not None:
        diagnosis_summary = recompute_patient_diagnosis(patient)

    cleaned_data, anomalies = compute_patient_glucose_stats(request.user)

    # Fetch all glucose logs and project next 3 timepoints
    try:
        logs_qs = GlucoseLog.objects.filter(profile=profile).order_by('timestamp')
        logs_data = list(logs_qs.values('timestamp', 'glucose_level'))

        if logs_data and len(logs_data) >= 2:
            first_ts = logs_data[0]['timestamp']
            hour_offsets = [
                (entry['timestamp'] - first_ts).total_seconds() / 3600.0
                for entry in logs_data
            ]
            glucose_values = [float(entry['glucose_level']) for entry in logs_data]
            slope, intercept = calculate_linear_regression(hour_offsets, glucose_values)

            if slope is None or intercept is None:
                raise ValueError('Unable to calculate glucose trend')

            # Project next 3 timepoints (assuming regular 4-hour intervals for future readings)
            last_ts = logs_data[-1]['timestamp']
            last_hours = hour_offsets[-1]

            for i in range(1, 4):
                future_hours = last_hours + (i * 4)  # assume 4-hour interval
                projected_value = int(round(slope * future_hours + intercept))
                projected_ts = last_ts + timedelta(hours=i * 4)
                
                # Save prediction
                GlucosePrediction.objects.create(
                    profile=profile,
                    target_timestamp=projected_ts,
                    predicted_value=max(0, projected_value),  # avoid negative
                    model='linear_trend',
                )
    except Exception as e:
        # silently handle errors
        pass

    # get upcoming predictions for next 24 hours
    now = timezone.now()
    end = now + timedelta(hours=24)
    preds_qs = profile.predictions.filter(target_timestamp__gte=now, target_timestamp__lte=end).order_by('target_timestamp')
    preds_list = list(preds_qs.values('target_timestamp', 'predicted_value'))

    # Calculate health metrics for summary card
    avg_glucose = 0
    safe_percentage = 0
    week_anomalies = 0

    if cleaned_data:
        # 1. Average glucose level over past 7 days
        glucose_values = [entry['glucose_level'] for entry in cleaned_data]
        avg_glucose = round(sum(glucose_values) / len(glucose_values), 1) if glucose_values else 0

        # 2. Percentage of readings in safe zone (< 140 mg/dL)
        safe_count = sum(1 for entry in cleaned_data if entry['glucose_level'] < 140)
        safe_percentage = round((safe_count / len(cleaned_data) * 100), 1) if cleaned_data else 0

    if anomalies:
        # 3. Count anomalies from the past 7 days
        one_week_ago = now - timedelta(days=7)
        for anomaly in anomalies:
            try:
                anomaly_ts = timezone.make_aware(timezone.datetime.fromisoformat(anomaly['timestamp'].replace('Z', '+00:00')))
                if anomaly_ts >= one_week_ago:
                    week_anomalies += 1
            except Exception:
                # if datetime parsing fails, count it anyway (conservative approach)
                week_anomalies += 1

    cleaned_json = json.dumps(cleaned_data)
    predictions_json = json.dumps(preds_list, default=str)

    # Get today's medications for the checklist
    today = timezone.now().date()
    today_medications = profile.medications.filter(date=today).order_by('scheduled_time')

    return render(request, 'patients/patient_dashboard.html', {
        'form': form,
        'cleaned_data': cleaned_data,
        'anomalies': anomalies,
        'cleaned_json': cleaned_json,
        'predictions_json': predictions_json,
        'avg_glucose': avg_glucose,
        'safe_percentage': safe_percentage,
        'week_anomalies': week_anomalies,
        'today_medications': today_medications,
        'diagnosis_summary': diagnosis_summary,
        'physician_users': physician_users,
        'available_physicians': available_physicians,
        'approved_physicians': approved_physicians,
        'allow_all_physicians': profile.allow_all_physicians,
    })


@login_required
def update_approved_physicians(request):
    if request.method != 'POST':
        return redirect('patients:patient_dashboard')

    profile, _ = PatientProfile.objects.get_or_create(user=request.user, defaults={'gestational_age_weeks': 0})
    valid_physician_ids = set(get_physician_users_queryset().values_list('id', flat=True))
    action = request.POST.get('action', 'add').strip()
    selected_value = request.POST.get('approved_physician', '').strip()
    selected_user_id = request.POST.get('approved_physician_id', '').strip()

    if action == 'remove':
        try:
            user_id = int(selected_user_id)
        except (TypeError, ValueError):
            user_id = None

        profile.allow_all_physicians = False
        profile.save(update_fields=['allow_all_physicians'])

        if user_id in valid_physician_ids:
            profile.approved_physicians.remove(user_id)
            messages.success(request, 'Physician removed from your approved list.')
        else:
            messages.error(request, 'Unable to remove physician. Please try again.')

        return redirect('patients:patient_dashboard')

    if action == 'clear_all':
        profile.allow_all_physicians = False
        profile.save(update_fields=['allow_all_physicians'])
        profile.approved_physicians.clear()
        messages.success(request, 'Approved physician list cleared.')
        return redirect('patients:patient_dashboard')

    if selected_value == '__all__':
        profile.allow_all_physicians = True
        profile.save(update_fields=['allow_all_physicians'])
        profile.approved_physicians.clear()
        messages.success(request, 'All physicians are now approved for your Chat with a Physician posts.')
        return redirect('patients:patient_dashboard')

    try:
        user_id = int(selected_value)
    except (TypeError, ValueError):
        user_id = None

    if user_id in valid_physician_ids:
        profile.allow_all_physicians = False
        profile.save(update_fields=['allow_all_physicians'])
        profile.approved_physicians.add(user_id)
        messages.success(request, 'Physician added to your approved list.')
    else:
        messages.error(request, 'Please select a valid physician.')

    return redirect('patients:patient_dashboard')


@login_required
def update_medication_status(request, medication_id):
    """AJAX endpoint to toggle medication taken status."""
    from django.http import JsonResponse
    
    profile = request.user.patient_profile
    medication = get_object_or_404(MedicationLog, id=medication_id, profile=profile)
    
    if request.method == 'POST':
        medication.taken = not medication.taken
        medication.save()
        return JsonResponse({
            'success': True,
            'medication_id': medication.id,
            'taken': medication.taken,
            'message': f"{'✓ Taken' if medication.taken else 'Not taken'}"
        })
    
    return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)


@login_required
def export_deidentified_csv(request):
    """Export de-identified glucose time-series joined to patient profile data.

    Access restricted to users in 'Clinician' or 'Biostatistician' groups.
    The CSV contains pseudonymized patient IDs (HMAC of profile pk) and removes names/emails/usernames.
    """
    user = request.user
    allowed = user.groups.filter(name__in=['Clinician', 'Biostatistician']).exists()
    if not allowed:
        return HttpResponseForbidden('You do not have permission to access this resource.')

    qs = GlucoseLog.objects.select_related('profile').order_by('profile_id', 'timestamp')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="deidentified_glucose_data.csv"'

    writer = csv.writer(response)
    # Header suitable for statistical software (wide but consistent)
    writer.writerow([
        'patient_pseudonym', 'profile_hash', 'gestational_age_weeks', 'target_fasting_glucose',
        'reading_timestamp_iso', 'glucose_level_mg_dl', 'meal_context'
    ])

    secret = settings.SECRET_KEY.encode('utf-8')
    for log in qs:
        profile = log.profile
        digest = hmac.new(secret, str(profile.pk).encode('utf-8'), hashlib.sha256).hexdigest()[:12]
        pseudonym = f"P{digest}"
        writer.writerow([
            pseudonym,
            digest,
            profile.gestational_age_weeks,
            profile.target_fasting_glucose,
            log.timestamp.isoformat(),
            log.glucose_level,
            log.get_meal_context_display(),
        ])

    return response


@login_required
def export_research_excel(request):
    """Export researcher dashboard data in an Excel workbook with a column meanings sheet."""
    if is_physician_user(request.user):
        patients = get_patients_approved_for_physician(request.user)
    else:
        patients = Patient.objects.all().order_by('last_name', 'first_name')

    # Build dynamic lab headers so each lab variable gets dedicated columns.
    lab_name_map = {}
    for lab_name in LabResult.objects.values_list('test_name', flat=True).distinct():
        if not lab_name:
            continue
        key = slugify(lab_name).replace('-', '_')
        if key and key not in lab_name_map:
            lab_name_map[key] = lab_name

    headers = [
        'patient_id',
        'first_name',
        'last_name',
        'date_of_birth',
        'gender',
        'email',
        'phone_number',
        'diagnosis_status',
        'diagnosis_confirmation',
        'diagnosis_reason',
        'latest_assessment_type',
        'latest_assessment_diabetes_type',
        'latest_fasting_glucose',
        'latest_post_meal_glucose',
        'latest_hba1c',
        'latest_classic_symptoms',
        'latest_insulin_use',
        'latest_oral_medication_use',
        'latest_medication_timing',
        'latest_current_medications',
        'latest_weight_kg',
        'latest_height_cm',
        'latest_bmi',
        'latest_waist_cm',
        'latest_medical_history',
        'latest_dietary_habits',
        'latest_lifestyle_factors',
        'latest_readiness_to_change',
    ]

    for key in sorted(lab_name_map.keys()):
        headers.extend([
            f'lab_{key}_value',
            f'lab_{key}_unit',
            f'lab_{key}_reference_range',
            f'lab_{key}_collected_at',
            f'lab_{key}_notes',
        ])

    max_sector_rows = 5
    for i in range(1, max_sector_rows + 1):
        headers.extend([
            f'prescription_{i}_title',
            f'prescription_{i}_content',
            f'prescription_{i}_created_at',
        ])

    for i in range(1, max_sector_rows + 1):
        headers.extend([
            f'blog_{i}_title',
            f'blog_{i}_category',
            f'blog_{i}_body',
            f'blog_{i}_published_at',
        ])

    for i in range(1, max_sector_rows + 1):
        headers.extend([
            f'comment_{i}_post_title',
            f'comment_{i}_post_category',
            f'comment_{i}_content',
            f'comment_{i}_created_at',
        ])

    header_meanings = {
        'patient_id': 'Internal patient record identifier.',
        'first_name': 'Patient first name.',
        'last_name': 'Patient last name.',
        'date_of_birth': 'Patient date of birth.',
        'gender': 'Patient recorded gender.',
        'email': 'Patient email address.',
        'phone_number': 'Patient phone number.',
        'diagnosis_status': 'Computed diabetes screening status from the rules engine.',
        'diagnosis_confirmation': 'Whether the computed diagnosis is confirmed, provisional, or not applicable.',
        'diagnosis_reason': 'Human-readable explanation for the computed diagnosis status.',
        'latest_assessment_type': 'Most recent assessment category entered for the patient.',
        'latest_assessment_diabetes_type': 'Most recent diabetes type selected in assessment.',
        'latest_fasting_glucose': 'Most recent fasting glucose entered in assessment.',
        'latest_post_meal_glucose': 'Most recent post-meal glucose entered in assessment.',
        'latest_hba1c': 'Most recent HbA1c entered in assessment.',
        'latest_classic_symptoms': 'Whether classic hyperglycemia symptoms were marked in the latest assessment.',
        'latest_insulin_use': 'Whether insulin use was marked in the latest assessment.',
        'latest_oral_medication_use': 'Whether oral diabetes medication use was marked in the latest assessment.',
        'latest_medication_timing': 'Timing of medications relative to meals from the latest assessment.',
        'latest_current_medications': 'Current medications entered in the latest assessment.',
        'latest_weight_kg': 'Latest recorded weight in kilograms.',
        'latest_height_cm': 'Latest recorded height in centimeters.',
        'latest_bmi': 'Latest recorded body mass index.',
        'latest_waist_cm': 'Latest recorded waist circumference in centimeters.',
        'latest_medical_history': 'Medical history entered in the latest assessment.',
        'latest_dietary_habits': 'Dietary habits entered in the latest assessment.',
        'latest_lifestyle_factors': 'Lifestyle factors entered in the latest assessment.',
        'latest_readiness_to_change': 'Readiness to change lifestyle entered in the latest assessment.',
    }

    for key, original_name in lab_name_map.items():
        header_meanings[f'lab_{key}_value'] = f'Latest value for lab test "{original_name}".'
        header_meanings[f'lab_{key}_unit'] = f'Unit for lab test "{original_name}".'
        header_meanings[f'lab_{key}_reference_range'] = f'Reference range for lab test "{original_name}".'
        header_meanings[f'lab_{key}_collected_at'] = f'Collection timestamp for lab test "{original_name}".'
        header_meanings[f'lab_{key}_notes'] = f'Notes for lab test "{original_name}".'

    for i in range(1, max_sector_rows + 1):
        header_meanings[f'prescription_{i}_title'] = f'Prescription {i} title, ordered from most recent to older records.'
        header_meanings[f'prescription_{i}_content'] = f'Prescription {i} content, ordered from most recent to older records.'
        header_meanings[f'prescription_{i}_created_at'] = f'Prescription {i} creation timestamp.'

    for i in range(1, max_sector_rows + 1):
        header_meanings[f'blog_{i}_title'] = f'Blog post {i} title, ordered from most recent to older records.'
        header_meanings[f'blog_{i}_category'] = f'Blog post {i} subgroup/category.'
        header_meanings[f'blog_{i}_body'] = f'Blog post {i} content/body.'
        header_meanings[f'blog_{i}_published_at'] = f'Blog post {i} publication timestamp.'

    for i in range(1, max_sector_rows + 1):
        header_meanings[f'comment_{i}_post_title'] = f'Comment {i} linked post title, ordered from most recent to older records.'
        header_meanings[f'comment_{i}_post_category'] = f'Comment {i} linked post subgroup/category.'
        header_meanings[f'comment_{i}_content'] = f'Comment {i} content/body.'
        header_meanings[f'comment_{i}_created_at'] = f'Comment {i} creation timestamp.'

    wb = Workbook()
    data_ws = wb.active
    data_ws.title = 'Research Data'
    meanings_ws = wb.create_sheet('Column Meanings')

    header_fill = PatternFill(fill_type='solid', fgColor='1D4ED8')
    header_font = Font(color='FFFFFF', bold=True)

    data_ws.append(headers)
    for cell in data_ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = cell.alignment.copy(wrap_text=True)

    meanings_ws.append(['column_name', 'meaning'])
    for cell in meanings_ws[1]:
        cell.fill = header_fill
        cell.font = header_font
    meanings_ws.freeze_panes = 'A2'

    for patient in patients:
        diagnosis = getattr(patient, 'diagnosis_summary', None)
        latest_assessment = patient.diabetes_assessments.order_by('-assessed_at').first()
        prescriptions = list(patient.prescriptions.order_by('-created_at')[:max_sector_rows])
        posts = list(patient.blog_posts.filter(published=True).order_by('-published_at')[:max_sector_rows])
        comments = list(patient.comments.select_related('post').order_by('-created_at')[:max_sector_rows])

        row = {h: 'N/A' for h in headers}
        row['patient_id'] = patient.pk
        row['first_name'] = _export_cell(patient.first_name)
        row['last_name'] = _export_cell(patient.last_name)
        row['date_of_birth'] = _export_cell(patient.date_of_birth)
        row['gender'] = _export_cell(patient.get_gender_display())
        row['email'] = _export_cell(patient.email)
        row['phone_number'] = _export_cell(patient.phone_number)

        if diagnosis:
            row['diagnosis_status'] = _export_cell(diagnosis.get_status_display())
            row['diagnosis_confirmation'] = _export_cell(diagnosis.get_confirmation_status_display())
            row['diagnosis_reason'] = _export_cell(diagnosis.reason)

        if latest_assessment:
            row['latest_assessment_type'] = _export_cell(latest_assessment.get_assessment_type_display())
            row['latest_assessment_diabetes_type'] = _export_cell(latest_assessment.get_diabetes_type_display() if latest_assessment.diabetes_type else None)
            row['latest_fasting_glucose'] = _export_cell(latest_assessment.fasting_glucose)
            row['latest_post_meal_glucose'] = _export_cell(latest_assessment.post_meal_glucose)
            row['latest_hba1c'] = _export_cell(latest_assessment.hba1c)
            if latest_assessment.classic_hyperglycemia_symptoms is not None:
                row['latest_classic_symptoms'] = 'Yes' if latest_assessment.classic_hyperglycemia_symptoms else 'No'
            if latest_assessment.insulin_use is not None:
                row['latest_insulin_use'] = 'Yes' if latest_assessment.insulin_use else 'No'
            if latest_assessment.oral_medication_use is not None:
                row['latest_oral_medication_use'] = 'Yes' if latest_assessment.oral_medication_use else 'No'
            row['latest_medication_timing'] = _export_cell(latest_assessment.medication_timing)
            row['latest_current_medications'] = _export_cell(latest_assessment.current_medications)
            row['latest_weight_kg'] = _export_cell(latest_assessment.weight_kg)
            row['latest_height_cm'] = _export_cell(latest_assessment.height_cm)
            row['latest_bmi'] = _export_cell(latest_assessment.bmi)
            row['latest_waist_cm'] = _export_cell(latest_assessment.waist_circumference_cm)
            row['latest_medical_history'] = _export_cell(latest_assessment.medical_history)
            row['latest_dietary_habits'] = _export_cell(latest_assessment.dietary_habits)
            row['latest_lifestyle_factors'] = _export_cell(latest_assessment.lifestyle_factors)
            row['latest_readiness_to_change'] = _export_cell(latest_assessment.get_readiness_to_change_display() if latest_assessment.readiness_to_change else None)

        latest_labs_by_key = {}
        for lab in patient.lab_results.order_by('-collected_at', '-created_at'):
            key = slugify(lab.test_name).replace('-', '_') if lab.test_name else ''
            if key and key in lab_name_map and key not in latest_labs_by_key:
                latest_labs_by_key[key] = lab

        for key in sorted(lab_name_map.keys()):
            lab = latest_labs_by_key.get(key)
            if not lab:
                continue
            row[f'lab_{key}_value'] = _export_cell(lab.result_value)
            row[f'lab_{key}_unit'] = _export_cell(lab.unit)
            row[f'lab_{key}_reference_range'] = _export_cell(lab.reference_range)
            row[f'lab_{key}_collected_at'] = _export_cell(lab.collected_at.isoformat() if lab.collected_at else None)
            row[f'lab_{key}_notes'] = _export_cell(lab.notes)

        for i, pres in enumerate(prescriptions, start=1):
            row[f'prescription_{i}_title'] = _export_cell(pres.title)
            row[f'prescription_{i}_content'] = _export_cell(pres.content)
            row[f'prescription_{i}_created_at'] = _export_cell(pres.created_at.isoformat() if pres.created_at else None)

        for i, post in enumerate(posts, start=1):
            row[f'blog_{i}_title'] = _export_cell(post.title)
            row[f'blog_{i}_category'] = _export_cell(post.get_category_display())
            row[f'blog_{i}_body'] = _export_cell(post.body)
            row[f'blog_{i}_published_at'] = _export_cell(post.published_at.isoformat() if post.published_at else None)

        for i, comment in enumerate(comments, start=1):
            row[f'comment_{i}_post_title'] = _export_cell(comment.post.title)
            row[f'comment_{i}_post_category'] = _export_cell(comment.post.get_category_display())
            row[f'comment_{i}_content'] = _export_cell(comment.content)
            row[f'comment_{i}_created_at'] = _export_cell(comment.created_at.isoformat() if comment.created_at else None)

        data_ws.append([row[h] for h in headers])

    for column_cells in data_ws.columns:
        max_length = 0
        column_letter = column_cells[0].column_letter
        for cell in column_cells:
            cell.alignment = cell.alignment.copy(wrap_text=True, vertical='top')
            try:
                cell_length = len(str(cell.value)) if cell.value is not None else 0
                max_length = max(max_length, cell_length)
            except Exception:
                pass
        data_ws.column_dimensions[column_letter].width = min(max_length + 2, 35)

    for column_name in headers:
        meanings_ws.append([column_name, header_meanings.get(column_name, 'N/A')])

    meanings_ws.column_dimensions['A'].width = 36
    meanings_ws.column_dimensions['B'].width = 90
    meanings_ws.freeze_panes = 'A2'

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    export_ts = timezone.now().strftime('%Y%m%d_%H%M%S')
    response['Content-Disposition'] = f'attachment; filename="research_patient_export_{export_ts}.xlsx"'
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    wb.save(response)
    return response


@login_required
def pwa_app(request):
    return redirect('patients:patient_dashboard')


@login_required
def doctor_dashboard(request):
    """Dashboard for doctors to monitor patient glucose anomalies and spikes."""
    # Get all alerts from the last 48 hours
    cutoff = timezone.now() - timedelta(hours=48)
    recent_alerts = DoctorAlert.objects.filter(created_at__gte=cutoff).select_related('patient_profile__user', 'glucose_log')

    # Build a patient anomaly count map
    from django.db.models import Count
    patient_alert_counts = (
        DoctorAlert.objects
        .filter(created_at__gte=cutoff)
        .values('patient_profile')
        .annotate(alert_count=Count('id'))
        .order_by('-alert_count')
    )

    # Get profile IDs ordered by alert count
    profile_ids = [item['patient_profile'] for item in patient_alert_counts]
    profiles = PatientProfile.objects.filter(id__in=profile_ids)
    profile_dict = {p.id: p for p in profiles}
    # reorder profiles by alert count
    sorted_profiles = [profile_dict[pid] for pid in profile_ids if pid in profile_dict]

    # pair each profile with its alert count
    profiles_with_counts = []
    for item in patient_alert_counts:
        if item['patient_profile'] in profile_dict:
            profiles_with_counts.append({
                'profile': profile_dict[item['patient_profile']],
                'alert_count': item['alert_count'],
                'alerts': recent_alerts.filter(patient_profile_id=item['patient_profile'])
            })

    return render(request, 'patients/doctor_dashboard.html', {
        'profiles_with_counts': profiles_with_counts,
        'recent_alerts': recent_alerts,
    })


def privacy_notice(request):
    """Render a simple privacy notice page."""
    return render(request, 'privacy_notice.html')


def terms_of_use(request):
    """Render a simple terms of use page."""
    return render(request, 'terms_of_use.html')

