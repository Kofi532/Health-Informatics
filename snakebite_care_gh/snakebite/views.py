from decimal import Decimal
from hmac import compare_digest
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import EducationalMaterial, EnvenomationType, FirstAidStep, HealthFacility, PatientAssessment, Region, Snake, Symptom
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

	error_message = ''
	if request.method == 'POST':
		password_input = request.POST.get('password', '')
		expected_password = getattr(settings, 'SNAKEBITE_APP_PASSWORD', 'Dr.EricNyarko')
		if compare_digest(password_input, expected_password):
			request.session[SNAKEBITE_ACCESS_SESSION_KEY] = True
			return redirect(next_url)
		error_message = 'Incorrect password. Please try again.'

	return render(
		request,
		'snakebite/access.html',
		{
			'next_url': next_url,
			'error_message': error_message,
		},
	)


@snakebite_password_required
def home_view(request):
	return render(request, 'snakebite/home.html')


def home(request):
	# Backward compatibility with any existing imports expecting home().
	return home_view(request)


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
