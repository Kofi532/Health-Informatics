from decimal import Decimal
from hmac import compare_digest
from urllib.parse import urlencode

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
	EducationalMaterial,
	EnvenomationType,
	FirstAidStep,
	HealthFacility,
	PatientAssessment,
	PatientCase,
	Referral,
	Region,
	Snake,
	SnakeSighting,
	Symptom,
)
from .services import SnakebiteRiskEngine, get_nearby_antivenom_facilities
from .serializers import (
	AssessmentCreateSerializer,
	AssessmentResultSerializer,
	EducationalMaterialSerializer,
	BootstrapPayloadSerializer,
	FirstAidStepSerializer,
	HealthFacilityStockSerializer,
	SnakeDetailSerializer,
	SnakeListSerializer,
)


SNAKEBITE_ACCESS_SESSION_KEY = 'snakebite_access_granted'
SNAKEBITE_NATIONALITY_SESSION_KEY = 'snakebite_nationality'
SNAKEBITE_MEMBER_TYPE_SESSION_KEY = 'snakebite_member_type'
SNAKEBITE_PASSWORD_VERIFIED_SESSION_KEY = 'snakebite_password_verified'

SNAKEBITE_NATIONALITY_OPTIONS = (
	('ghana', 'Ghana'),
	('malawi', 'Malawi'),
	('kenya', 'Kenya'),
	('nigeria', 'Nigeria'),
	('zambia', 'Zambia'),
)

SNAKEBITE_MEMBER_TYPE_OPTIONS = (
	('healthcare', 'Healthcare Member'),
	('community', 'Community Member'),
)


def snakebite_password_required(view_func):
	def wrapped_view(request, *args, **kwargs):
		if request.session.get(SNAKEBITE_ACCESS_SESSION_KEY):
			return view_func(request, *args, **kwargs)

		query = urlencode({'next': request.get_full_path()})
		return redirect(f"{reverse('snakebite:access')}?{query}")

	return wrapped_view


def access_view(request):
	next_url = request.GET.get('next') or request.POST.get('next') or reverse('snakebite:home')
	if not next_url.startswith('/snakebite/'):
		next_url = reverse('snakebite:home')

	reset_access = (request.GET.get('reset_access') or request.POST.get('reset_access')) == '1'
	if reset_access:
		request.session.pop(SNAKEBITE_ACCESS_SESSION_KEY, None)
		request.session.pop(SNAKEBITE_PASSWORD_VERIFIED_SESSION_KEY, None)
		request.session.pop(SNAKEBITE_NATIONALITY_SESSION_KEY, None)
		request.session.pop(SNAKEBITE_MEMBER_TYPE_SESSION_KEY, None)

	change_profile_requested = (request.GET.get('change_profile') or request.POST.get('change_profile')) == '1'
	password_verified = bool(request.session.get(SNAKEBITE_PASSWORD_VERIFIED_SESSION_KEY))
	access_granted = bool(request.session.get(SNAKEBITE_ACCESS_SESSION_KEY))
	can_edit_profile = password_verified or (access_granted and change_profile_requested)
	show_profile_form = request.GET.get('step') == 'profile' and can_edit_profile

	if request.method == 'GET' and access_granted and not change_profile_requested and request.GET.get('step') != 'profile' and not reset_access:
		return redirect(next_url)

	if request.method == 'GET' and password_verified and request.GET.get('step') != 'profile':
		return redirect(f"{reverse('snakebite:access')}?{urlencode({'next': next_url, 'step': 'profile'})}")

	nationality_values = {value for value, _ in SNAKEBITE_NATIONALITY_OPTIONS}
	member_type_values = {value for value, _ in SNAKEBITE_MEMBER_TYPE_OPTIONS}
	error_message = ''
	selected_nationality = request.session.get(SNAKEBITE_NATIONALITY_SESSION_KEY, '')
	selected_member_type = request.session.get(SNAKEBITE_MEMBER_TYPE_SESSION_KEY, '')
	if request.method == 'POST':
		action = request.POST.get('action', 'password')

		if action == 'password':
			password_input = request.POST.get('password', '')
			expected_password = 'Dr.EricNyarko'
			if not compare_digest(password_input, expected_password):
				error_message = 'Incorrect password. Please try again.'
			else:
				request.session[SNAKEBITE_PASSWORD_VERIFIED_SESSION_KEY] = True
				return redirect(f"{reverse('snakebite:access')}?{urlencode({'next': next_url, 'step': 'profile'})}")

		elif action == 'profile':
			if not can_edit_profile:
				error_message = 'Please confirm your password first.'
			else:
				selected_nationality = request.POST.get('nationality', '').strip().lower()
				selected_member_type = request.POST.get('member_type', '').strip().lower()
				if selected_nationality not in nationality_values:
					error_message = 'Please select your nationality to continue.'
				elif selected_member_type not in member_type_values:
					error_message = 'Please select whether you are a Healthcare or Community member.'
				else:
					request.session[SNAKEBITE_ACCESS_SESSION_KEY] = True
					request.session[SNAKEBITE_NATIONALITY_SESSION_KEY] = selected_nationality
					request.session[SNAKEBITE_MEMBER_TYPE_SESSION_KEY] = selected_member_type
					request.session.pop(SNAKEBITE_PASSWORD_VERIFIED_SESSION_KEY, None)
					if selected_member_type == 'community':
						return redirect(reverse('snakebite:community_home'))
					if selected_member_type == 'healthcare':
						return redirect(reverse('snakebite:chw_home'))
					return redirect(next_url)
		else:
			error_message = 'Invalid request. Please try again.'

	return render(
		request,
		'snakebite/access.html',
		{
			'next_url': next_url,
			'error_message': error_message,
			'nationality_options': SNAKEBITE_NATIONALITY_OPTIONS,
			'member_type_options': SNAKEBITE_MEMBER_TYPE_OPTIONS,
			'selected_nationality': selected_nationality,
			'selected_member_type': selected_member_type,
			'show_profile_form': show_profile_form,
			'can_edit_profile': can_edit_profile,
			'change_profile_requested': change_profile_requested,
		},
	)


@snakebite_password_required
def home_view(request):
	member_type = request.session.get(SNAKEBITE_MEMBER_TYPE_SESSION_KEY, '')
	if member_type == 'community':
		return redirect('snakebite:community_home')
	if member_type == 'healthcare':
		return redirect('snakebite:chw_home')
	return render(request, 'snakebite/home.html')


@snakebite_password_required
def community_home_view(request):
	return render(
		request,
		'snakebite/community_home.html',
		{
			'nationality_label': request.session.get(SNAKEBITE_NATIONALITY_SESSION_KEY, ''),
			'member_type_label': request.session.get(SNAKEBITE_MEMBER_TYPE_SESSION_KEY, ''),
		},
	)


@snakebite_password_required
def community_bite_assessment_view(request):
	if request.method == 'POST':
		return redirect('snakebite:community_risk_result')
	return render(
		request,
		'snakebite/bite_assessment.html',
		{
			'nationality_label': request.session.get(SNAKEBITE_NATIONALITY_SESSION_KEY, ''),
			'member_type_label': request.session.get(SNAKEBITE_MEMBER_TYPE_SESSION_KEY, ''),
		},
	)


@snakebite_password_required
def community_risk_result_view(request):
	return render(
		request,
		'snakebite/risk_result.html',
		{
			'nationality_label': request.session.get(SNAKEBITE_NATIONALITY_SESSION_KEY, ''),
			'member_type_label': request.session.get(SNAKEBITE_MEMBER_TYPE_SESSION_KEY, ''),
		},
	)


@snakebite_password_required
def community_nearest_help_view(request):
	return render(
		request,
		'snakebite/nearest_help.html',
		{
			'nationality_label': request.session.get(SNAKEBITE_NATIONALITY_SESSION_KEY, ''),
			'member_type_label': request.session.get(SNAKEBITE_MEMBER_TYPE_SESSION_KEY, ''),
		},
	)


@snakebite_password_required
def report_sighting_view(request):
	species = Snake.objects.order_by('common_name')
	time_options = SnakeSighting.TimeSeenChoices.choices
	form_errors = []

	if request.method == 'POST':
		heading = (request.POST.get('headline') or '').strip()
		description = (request.POST.get('description') or '').strip()
		photo = request.FILES.get('photo')
		species_id = request.POST.get('suspected_species')
		species_obj = Snake.objects.filter(pk=species_id).first() if species_id else None
		was_bitten = request.POST.get('was_bitten') == 'yes'
		contact_number = (request.POST.get('contact_number') or '').strip()
		time_seen = request.POST.get('time_seen') or SnakeSighting.TimeSeenChoices.JUST_NOW

		if not heading:
			form_errors.append('Headline is required.')
		if not description:
			form_errors.append('Please add a short description.')
		if not photo:
			form_errors.append('Please upload a photo.')

		if not form_errors:
			sighting = SnakeSighting.objects.create(
				photo=photo,
				headline=heading,
				description=description,
				was_bitten=was_bitten,
				contact_number=contact_number,
				time_seen=time_seen,
				suspected_species=species_obj,
			)
			case = PatientCase.objects.create(
				patient_name=heading[:150] or 'Reported snake case',
				patient_age=18,
				gender=PatientCase.Gender.FEMALE if not was_bitten else PatientCase.Gender.OTHER,
				location='Reported from field',
				symptoms=description,
				suspected_snake_type=species_obj.common_name if species_obj else 'Unspecified',
				risk_level=PatientCase.RiskLevel.HIGH if was_bitten else PatientCase.RiskLevel.MEDIUM,
				status=PatientCase.Status.OPEN,
				clinical_notes=(
					f"Reported via snake sighting. "
					f"Contact: {contact_number or 'Not provided'}. "
					f"Was bitten: {'Yes' if was_bitten else 'No'}. "
					f"Time seen: {dict(SnakeSighting.TimeSeenChoices.choices).get(time_seen, time_seen)}."
				),
				photo=photo,
			)
			return redirect('snakebite:case_details', pk=case.pk)

	return render(
		request,
		'snakebite/report_sighting.html',
		{
			'species': species,
			'time_options': time_options,
			'form_errors': form_errors,
		},
	)


def home(request):
	# Backward compatibility with any existing imports expecting home().
	return home_view(request)


def _get_dashboard_summary():
	cases = PatientCase.objects.order_by('-created_at')
	active_cases = cases.filter(status__in=[PatientCase.Status.OPEN, PatientCase.Status.IN_TRANSIT])
	metric_cards = [
		{
			'key': 'active_cases',
			'label': 'Active Cases',
			'count': active_cases.count(),
			'url_name': 'case_metric_list',
			'url_param': 'active_cases',
		},
		{
			'key': 'risk_alerts',
			'label': 'Risk Alerts',
			'count': cases.filter(risk_level=PatientCase.RiskLevel.HIGH).count(),
			'url_name': 'case_metric_list',
			'url_param': 'risk_alerts',
		},
		{
			'key': 'referrals',
			'label': 'Referrals',
			'count': Referral.objects.filter(status__in=[Referral.Status.PENDING, Referral.Status.SENT]).count(),
			'url_name': 'case_metric_list',
			'url_param': 'referrals',
		},
		{
			'key': 'resolved',
			'label': 'Resolved',
			'count': cases.filter(status=PatientCase.Status.RESOLVED).count(),
			'url_name': 'case_metric_list',
			'url_param': 'resolved',
		},
	]
	latest_case = active_cases.first()
	return {
		'cases': cases,
		'active_cases': active_cases,
		'latest_case': latest_case,
		'priority_cases': active_cases[:4],
		'metric_cards': metric_cards,
		'total_cases': cases.count(),
		'high_risk_cases': cases.filter(risk_level=PatientCase.RiskLevel.HIGH).count(),
		'referrals_made': Referral.objects.count(),
		'completed_outcomes': cases.filter(status=PatientCase.Status.RESOLVED).count(),
		'new_alerts': cases.filter(risk_level=PatientCase.RiskLevel.HIGH, status=PatientCase.Status.OPEN).count(),
		'pending_referrals': Referral.objects.filter(status__in=[Referral.Status.PENDING, Referral.Status.SENT]).count(),
		'resource_count': EducationalMaterial.objects.count(),
	}


@method_decorator(snakebite_password_required, name='dispatch')
class CHWHomeView(View):
	def get(self, request, *args, **kwargs):
		member_type = request.session.get(SNAKEBITE_MEMBER_TYPE_SESSION_KEY, '').lower()
		if member_type and member_type != 'healthcare':
			return redirect('snakebite:home')

		dashboard = _get_dashboard_summary()
		user_name = request.user.get_full_name() if getattr(request.user, 'is_authenticated', False) and request.user.get_full_name() else 'Ama Mensah'
		role_label = 'CHW'
		return render(
			request,
			'snakebite/chw_home.html',
			{
				'user_name': user_name,
				'role_label': role_label,
				'active_cases': dashboard['active_cases'].count(),
				'new_alerts': dashboard['new_alerts'],
				'pending_referrals': dashboard['pending_referrals'],
				'resource_count': dashboard['resource_count'],
				'priority_cases': dashboard['priority_cases'],
				'latest_case': dashboard['latest_case'],
				'metric_cards': dashboard['metric_cards'],
			},
		)


@method_decorator(snakebite_password_required, name='dispatch')
class CaseDetailsView(View):
	def get(self, request, pk, *args, **kwargs):
		active_cases = PatientCase.objects.filter(status__in=[PatientCase.Status.OPEN, PatientCase.Status.IN_TRANSIT]).order_by('-created_at')
		case = active_cases.filter(pk=pk).first()
		if case is None:
			case = active_cases.first()
		if case is None:
			return redirect('snakebite:chw_home')
		symptoms = [item.strip() for item in case.symptoms.splitlines() if item.strip()] or [
			'Severe pain',
			'Swelling',
			'Bleeding',
		]
		return render(
			request,
			'snakebite/case_details.html',
			{
				'case': case,
				'symptoms': symptoms,
				'active_cases': active_cases,
			},
		)


@method_decorator(snakebite_password_required, name='dispatch')
class SendReferralView(View):
	def get(self, request, pk, *args, **kwargs):
		case = PatientCase.objects.filter(pk=pk).first()
		if case is None:
			latest_case = PatientCase.objects.order_by('-created_at').first()
			if latest_case is None:
				return redirect('snakebite:chw_home')
			return redirect('snakebite:send_referral', pk=latest_case.pk)
		facility = HealthFacility.objects.filter(antivenom_available=True).order_by('name').first() or HealthFacility.objects.order_by('name').first()
		facilities = HealthFacility.objects.order_by('name')
		default_note = 'High risk envenoming. Patient stabilised and on the way.'
		return render(
			request,
			'snakebite/send_referral.html',
			{
				'case': case,
				'facility': facility,
				'facilities': facilities,
				'default_note': default_note,
			},
		)

	def post(self, request, pk, *args, **kwargs):
		case = PatientCase.objects.filter(pk=pk).first()
		if case is None:
			latest_case = PatientCase.objects.order_by('-created_at').first()
			if latest_case is None:
				return redirect('snakebite:chw_home')
			return redirect('snakebite:send_referral', pk=latest_case.pk)
		facility_id = request.POST.get('facility_id')
		facility = HealthFacility.objects.filter(pk=facility_id).first() if facility_id else None
		if facility is None:
			facility = HealthFacility.objects.filter(antivenom_available=True).order_by('name').first() or HealthFacility.objects.order_by('name').first()
		note = request.POST.get('referral_note', 'High risk envenoming. Patient stabilised and on the way.')
		share_details = request.POST.get('share_details') == 'on'
		referral = Referral.objects.create(
			case=case,
			destination_facility=facility,
			notes=note,
			shared_patient_details=share_details,
			status=Referral.Status.SENT,
		)
		case.status = PatientCase.Status.IN_TRANSIT
		case.save(update_fields=['status'])
		return redirect('snakebite:case_details', pk=case.pk)


@method_decorator(snakebite_password_required, name='dispatch')
class CHWDashboardView(View):
	def get(self, request, *args, **kwargs):
		dashboard = _get_dashboard_summary()
		recent_alerts = []
		for case in dashboard['cases'][:3]:
			recent_alerts.append({
				'time': case.created_at,
				'message': f"High risk case reported: {case.case_id}",
			})
		for referral in Referral.objects.order_by('-sent_at')[:2]:
			recent_alerts.append({
				'time': referral.sent_at,
				'message': f"Transport requested for {referral.case.case_id}",
			})
		recent_alerts.sort(key=lambda item: item['time'], reverse=True)
		return render(
			request,
			'snakebite/chw_dashboard.html',
			{
				'total_cases': dashboard['total_cases'],
				'high_risk_cases': dashboard['high_risk_cases'],
				'referrals_made': dashboard['referrals_made'],
				'completed_outcomes': dashboard['completed_outcomes'],
				'recent_alerts': recent_alerts[:5],
				'metric_cards': dashboard['metric_cards'],
				'latest_case': dashboard['latest_case'],
			},
		)


@snakebite_password_required
def case_metric_list_view(request, metric):
	metric_map = {
		'active_cases': {
			'label': 'Active Cases',
			'queryset': PatientCase.objects.filter(status__in=[PatientCase.Status.OPEN, PatientCase.Status.IN_TRANSIT]).order_by('-created_at'),
		},
		'risk_alerts': {
			'label': 'Risk Alerts',
			'queryset': PatientCase.objects.filter(risk_level=PatientCase.RiskLevel.HIGH).order_by('-created_at'),
		},
		'referrals': {
			'label': 'Referrals',
			'queryset': PatientCase.objects.filter(referrals__isnull=False).distinct().order_by('-created_at'),
		},
		'resolved': {
			'label': 'Resolved',
			'queryset': PatientCase.objects.filter(status=PatientCase.Status.RESOLVED).order_by('-created_at'),
		},
	}
	metric_config = metric_map.get(metric)
	if metric_config is None:
		return redirect('snakebite:chw_home')

	latest_case = PatientCase.objects.filter(status__in=[PatientCase.Status.OPEN, PatientCase.Status.IN_TRANSIT]).order_by('-created_at').first()
	return render(
		request,
		'snakebite/case_metric_list.html',
		{
			'metric': metric,
			'metric_label': metric_config['label'],
			'cases': metric_config['queryset'],
			'latest_case': latest_case,
		},
	)


@snakebite_password_required
def first_aid_view(request):
	first_aid_steps = FirstAidStep.objects.order_by('step_number')
	emergency_number = '112'
	return render(
		request,
		'snakebite/first_aid.html',
		{
			'first_aid_steps': first_aid_steps,
			'emergency_number': emergency_number,
		},
	)


@snakebite_password_required
def identify_symptoms_view(request):
	symptoms = Symptom.objects.order_by('body_system', 'name')
	symptoms_by_system = {}

	def icon_for_symptom(body_system, symptom_name):
		body_system_lower = body_system.lower()
		symptom_name_lower = symptom_name.lower()

		if 'resp' in body_system_lower or 'breath' in symptom_name_lower:
			return 'lungs'
		if 'neuro' in body_system_lower or 'ptosis' in symptom_name_lower:
			return 'brain'
		if 'hemo' in body_system_lower or 'bleed' in symptom_name_lower:
			return 'drop'
		if 'renal' in body_system_lower or 'urine' in symptom_name_lower:
			return 'kidney'
		if 'cardio' in body_system_lower:
			return 'heart'
		if 'skin' in body_system_lower or 'swell' in symptom_name_lower:
			return 'bandage'
		return 'stethoscope'

	for symptom in symptoms:
		symptoms_by_system.setdefault(symptom.body_system, []).append(
			{
				'symptom': symptom,
				'icon': icon_for_symptom(symptom.body_system, symptom.name),
			}
		)

	assessment_result = None
	selected_symptoms = []
	if request.method == 'POST':
		selected_symptoms = request.POST.getlist('symptoms')
		engine = SnakebiteRiskEngine()
		assessment_result = engine.assess_risk(selected_symptoms)

	return render(
		request,
		'snakebite/identify_symptoms.html',
		{
			'symptoms': symptoms,
			'symptoms_by_system': symptoms_by_system,
			'selected_symptoms': set(selected_symptoms),
			'assessment_result': assessment_result,
		},
	)


@snakebite_password_required
def snakes_in_area_view(request):
	regions = Region.objects.order_by('name')
	active_region_id = request.GET.get('region_id')

	if not active_region_id and request.user.is_authenticated:
		if getattr(request.user, 'region_id', None):
			active_region_id = str(request.user.region_id)
		elif getattr(request.user, 'region', None) and getattr(request.user.region, 'id', None):
			active_region_id = str(request.user.region.id)

	if not active_region_id:
		default_region = Region.objects.filter(snakes__isnull=False).order_by('name').first() or Region.objects.order_by('name').first()
		if default_region is not None:
			active_region_id = str(default_region.id)

	snakes = Snake.objects.prefetch_related('region_distribution').all().order_by('common_name')
	active_region = None
	if active_region_id:
		snakes = snakes.filter(region_distribution__id=active_region_id).distinct()
		active_region = Region.objects.filter(id=active_region_id).first()

	selected_snake = None
	selected_snake_id = request.GET.get('snake_id')
	if selected_snake_id:
		selected_snake = snakes.filter(id=selected_snake_id).first()

	return render(
		request,
		'snakebite/snakes_in_area.html',
		{
			'regions': regions,
			'active_region_id': active_region_id,
			'active_region': active_region,
			'snakes': snakes,
			'selected_snake': selected_snake,
		},
	)


@snakebite_password_required
def education_training_view(request):
	category_config = [
		{'key': 'guideline', 'label': 'Guidelines', 'icon': 'clipboard'},
		{'key': 'first_aid', 'label': 'First Aid', 'icon': 'medical-bag'},
		{'key': 'biology', 'label': 'Biology', 'icon': 'dna'},
		{'key': 'video', 'label': 'Videos', 'icon': 'play'},
		{'key': 'poster', 'label': 'Posters', 'icon': 'poster'},
	]

	materials = EducationalMaterial.objects.order_by('category', 'title')
	grouped_categories = []
	for config in category_config:
		category_key = config['key']
		if category_key in {'first_aid', 'biology'}:
			category_materials = materials.none()
		else:
			category_materials = materials.filter(category=category_key)

		material_items = []
		for item in category_materials:
			download_url = item.file_attachment.url if item.file_attachment else ''
			resource_url = download_url or item.video_url
			material_items.append(
				{
					'id': item.id,
					'title': item.title,
					'category': item.category,
					'download_url': download_url,
					'video_url': item.video_url,
					'resource_url': resource_url,
					'is_downloadable': bool(download_url),
					'file_size_bytes': item.file_attachment.size if item.file_attachment else None,
					'offline_available': bool(download_url),
				}
			)

		grouped_categories.append(
			{
				'key': category_key,
				'label': config['label'],
				'icon': config['icon'],
				'total': len(material_items),
				'materials': material_items,
			}
		)

	category_totals = {category['key']: category['total'] for category in grouped_categories}

	return render(
		request,
		'snakebite/education_training.html',
		{
			'grouped_categories': grouped_categories,
			'category_totals': category_totals,
		},
	)


@snakebite_password_required
def antivenom_map_view(request):
	facilities = HealthFacility.objects.select_related('region').filter(antivenom_available=True).order_by('region__name', 'name')
	facilities_payload = []
	for facility in facilities:
		latitude = float(facility.latitude) if facility.latitude is not None else None
		longitude = float(facility.longitude) if facility.longitude is not None else None
		facilities_payload.append(
			{
				'id': facility.id,
				'name': facility.name,
				'facility_type': facility.get_facility_type_display(),
				'region': facility.region.name,
				'latitude': latitude,
				'longitude': longitude,
				'antivenom_available': facility.antivenom_available,
				'antivenom_cost': float(facility.antivenom_cost) if facility.antivenom_cost is not None else None,
				'contact_number': facility.contact_number,
			}
		)

	return render(
		request,
		'snakebite/antivenom_map.html',
		{
			'facilities': facilities,
			'facilities_payload': facilities_payload,
		},
	)


@snakebite_password_required
def resources_view(request):
	return render(request, 'snakebite/resources.html')


@snakebite_password_required
def settings_view(request):
	return render(
		request,
		'snakebite/settings.html',
		{
			'language': 'English',
			'alert_radius': '500m',
			'nearest_catchers': [],
			'regions': Region.objects.order_by('name'),
			'emergency_number': '112',
		},
	)


class SnakeViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = Snake.objects.prefetch_related('region_distribution').all()

	def get_serializer_class(self):
		if self.action == 'retrieve':
			return SnakeDetailSerializer
		return SnakeListSerializer


class FirstAidStepViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = FirstAidStep.objects.all().order_by('step_number')
	serializer_class = FirstAidStepSerializer


class EducationalMaterialViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = EducationalMaterial.objects.all().order_by('category', 'title')
	serializer_class = EducationalMaterialSerializer


class HealthFacilityStockViewSet(viewsets.ReadOnlyModelViewSet):
	queryset = HealthFacility.objects.select_related('region').all()
	serializer_class = HealthFacilityStockSerializer

	def get_queryset(self):
		queryset = super().get_queryset()
		region = self.request.query_params.get('region')
		antivenom_available = self.request.query_params.get('antivenom_available')

		if region:
			queryset = queryset.filter(region_id=region)
		if antivenom_available is not None:
			truthy_values = {'1', 'true', 'yes', 'on'}
			queryset = queryset.filter(antivenom_available=antivenom_available.lower() in truthy_values)

		return queryset.order_by('name')

	def get_serializer_context(self):
		context = super().get_serializer_context()
		patient_latitude = self.request.query_params.get('patient_latitude') or None
		patient_longitude = self.request.query_params.get('patient_longitude') or None
		context['patient_location'] = {
			'latitude': patient_latitude,
			'longitude': patient_longitude,
		}
		return context


class AssessmentCreateView(APIView):
	def post(self, request, *args, **kwargs):
		serializer = AssessmentCreateSerializer(data=request.data)
		serializer.is_valid(raise_exception=True)

		engine = SnakebiteRiskEngine()
		symptom_slugs = [symptom.slug for symptom in serializer.validated_data['symptoms_list']]
		assessment_result = engine.assess_risk(symptom_slugs)

		with transaction.atomic():
			assessment = PatientAssessment.objects.create(
				region=serializer.validated_data['region'],
				patient_age_group=serializer.validated_data['patient_age_group'],
				recommended_action='\n'.join(assessment_result['recommended_actions']),
			)
			assessment.symptoms_present.set(serializer.validated_data['symptoms_list'])

			predicted_envenomation = self._resolve_prediction(assessment_result['predicted_envenomation'])
			if predicted_envenomation is not None:
				assessment.predicted_envenomation = predicted_envenomation
				assessment.save(update_fields=['predicted_envenomation'])

			PatientAssessment.objects.filter(pk=assessment.pk).update(
				severity_score=assessment_result['severity_score'],
				risk_level=self._normalize_risk_level(assessment_result['risk_level']),
				recommended_action='\n'.join(assessment_result['recommended_actions']),
			)
			assessment.refresh_from_db()

		nearest_facility = self._nearest_stocked_facility(assessment, serializer.validated_data)

		payload = {
			'assessment_id': assessment.pk,
			'risk_level': assessment_result['risk_level'],
			'predicted_envenomation': assessment_result['predicted_envenomation'],
			'recommended_actions': assessment_result['recommended_actions'],
			'likely_snakes': assessment_result['likely_snakes'],
			'nearest_facility': nearest_facility,
			'severity_score': assessment_result['severity_score'],
		}
		output_serializer = AssessmentResultSerializer(payload)
		return Response(output_serializer.data, status=status.HTTP_201_CREATED)

	def _normalize_risk_level(self, risk_level):
		mapping = {
			'HIGH RISK': PatientAssessment.RiskLevel.HIGH,
			'MEDIUM RISK': PatientAssessment.RiskLevel.MEDIUM,
			'LOW RISK': PatientAssessment.RiskLevel.LOW,
		}
		return mapping.get(risk_level, PatientAssessment.RiskLevel.LOW)

	def _resolve_prediction(self, predicted_envenomation):
		if predicted_envenomation in {'Neurotoxic', 'Hemotoxic'}:
			return EnvenomationType.objects.filter(type_name__iexact=predicted_envenomation).first()
		return None

	def _nearest_stocked_facility(self, assessment, validated_data):
		patient_latitude = validated_data.get('patient_latitude')
		patient_longitude = validated_data.get('patient_longitude')

		queryset = HealthFacility.objects.select_related('region').filter(antivenom_available=True)
		region_id = assessment.region_id
		if region_id:
			queryset = queryset.filter(region_id=region_id)

		facilities = list(queryset)
		if not facilities:
			return None

		if patient_latitude is None or patient_longitude is None:
			facility = facilities[0]
			return HealthFacilityStockSerializer(facility).data

		best_facility = min(
			facilities,
			key=lambda facility: self._distance_km(
				Decimal(str(patient_latitude)),
				Decimal(str(patient_longitude)),
				facility.latitude,
				facility.longitude,
			),
		)
		context = {
			'patient_location': {
				'latitude': patient_latitude,
				'longitude': patient_longitude,
			}
		}
		return HealthFacilityStockSerializer(best_facility, context=context).data

	def _distance_km(self, patient_latitude, patient_longitude, facility_latitude, facility_longitude):
		if facility_latitude is None or facility_longitude is None:
			return float('inf')

		from math import atan2, cos, radians, sin, sqrt

		earth_radius_km = 6371.0
		latitude_delta = radians(float(facility_latitude - patient_latitude))
		longitude_delta = radians(float(facility_longitude - patient_longitude))
		patient_latitude_rad = radians(float(patient_latitude))
		facility_latitude_rad = radians(float(facility_latitude))
		a = sin(latitude_delta / 2) ** 2 + cos(patient_latitude_rad) * cos(facility_latitude_rad) * sin(longitude_delta / 2) ** 2
		return 2 * earth_radius_km * atan2(sqrt(a), sqrt(1 - a))


class SyncBootstrapView(APIView):
	def get(self, request, *args, **kwargs):
		snakes = Snake.objects.prefetch_related('region_distribution').all()
		health_facilities = HealthFacility.objects.select_related('region').all()

		payload = {
			'snakes': SnakeDetailSerializer(snakes, many=True).data,
			'health_facilities': HealthFacilityStockSerializer(health_facilities, many=True).data,
			'emergency_guides': [
				{
					'title': 'First Aid',
					'steps': [
						'Keep the patient calm and still.',
						'Splint the limb and remove constricting items.',
						'Do NOT cut, suck, or apply ice to the bite.',
					],
				},
				{
					'title': 'Referral',
					'steps': [
						'Urgently refer to the nearest equipped facility.',
						'Administer antivenom only in a clinical setting.',
					],
				},
			],
			'educational_content': [
				{
					'title': 'Recognize high-risk symptoms',
					'summary': 'Drooping eyelids, breathing difficulty, bleeding gums, and dark urine require urgent escalation.',
				},
				{
					'title': 'Stay prepared',
					'summary': 'Carry emergency contacts and know the nearest stocked health facility before travel.',
				},
			],
		}
		return Response(BootstrapPayloadSerializer(payload).data)


class NearbyAntivenomFacilitiesView(APIView):
	def get(self, request, *args, **kwargs):
		latitude = request.query_params.get('latitude')
		longitude = request.query_params.get('longitude')
		max_distance_km = request.query_params.get('max_distance_km', 50)
		region_id = request.query_params.get('region_id')

		if latitude is None or longitude is None:
			return Response(
				{'detail': 'latitude and longitude are required.'},
				status=status.HTTP_400_BAD_REQUEST,
			)

		nearby_facilities = get_nearby_antivenom_facilities(
			latitude=latitude,
			longitude=longitude,
			max_distance_km=max_distance_km,
			region_id=region_id,
		)
		return Response(
			{
				'count': len(nearby_facilities),
				'results': nearby_facilities,
			}
		)
