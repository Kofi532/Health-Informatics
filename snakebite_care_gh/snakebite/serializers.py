from decimal import Decimal
from math import atan2, cos, radians, sin, sqrt

from django.db.models import QuerySet
from rest_framework import serializers

from .models import EducationalMaterial, EnvenomationType, FirstAidStep, HealthFacility, PatientAssessment, Region, Snake, Symptom


class RegionLookupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Region
        fields = ["id", "name", "code"]


class SnakeListSerializer(serializers.ModelSerializer):
    region_lookup = RegionLookupSerializer(source="region_distribution", many=True, read_only=True)
    venom_classification = serializers.SerializerMethodField()

    class Meta:
        model = Snake
        fields = [
            "id",
            "common_name",
            "scientific_name",
            "venom_type",
            "venom_classification",
            "region_lookup",
        ]

    def get_venom_classification(self, obj):
        return {
            "venom_type": obj.venom_type,
            "label": obj.get_venom_type_display(),
        }


class SnakeDetailSerializer(SnakeListSerializer):
    region_lookup = RegionLookupSerializer(source="region_distribution", many=True, read_only=True)

    class Meta(SnakeListSerializer.Meta):
        fields = SnakeListSerializer.Meta.fields + [
            "description",
            "visual_features",
            "image",
        ]


class HealthFacilityStockSerializer(serializers.ModelSerializer):
    region = RegionLookupSerializer(read_only=True)
    location = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()
    antivenom_cost_ghs = serializers.SerializerMethodField()

    class Meta:
        model = HealthFacility
        fields = [
            "id",
            "name",
            "facility_type",
            "region",
            "latitude",
            "longitude",
            "location",
            "contact_number",
            "antivenom_available",
            "antivenom_cost_ghs",
            "last_stock_update",
            "distance_km",
        ]

    def get_location(self, obj):
        return {
            "latitude": obj.latitude,
            "longitude": obj.longitude,
        }

    def get_distance_km(self, obj):
        patient_location = self.context.get("patient_location") or {}
        patient_latitude = patient_location.get("latitude")
        patient_longitude = patient_location.get("longitude")

        if patient_latitude is None or patient_longitude is None:
            return None

        if obj.latitude is None or obj.longitude is None:
            return None

        return round(
            self._haversine(
                Decimal(str(patient_longitude)),
                Decimal(str(patient_latitude)),
                obj.longitude,
                obj.latitude,
            ),
            2,
        )

    def get_antivenom_cost_ghs(self, obj):
        if obj.antivenom_cost is None:
            return None
        return f"GHS {obj.antivenom_cost:.2f}"

    def _haversine(self, patient_longitude, patient_latitude, facility_longitude, facility_latitude):
        earth_radius_km = Decimal("6371")
        longitude_delta = radians(float(facility_longitude - patient_longitude))
        latitude_delta = radians(float(facility_latitude - patient_latitude))
        patient_latitude_rad = radians(float(patient_latitude))
        facility_latitude_rad = radians(float(facility_latitude))

        a = sin(latitude_delta / 2) ** 2 + cos(patient_latitude_rad) * cos(facility_latitude_rad) * sin(longitude_delta / 2) ** 2
        return float(2 * earth_radius_km * atan2(sqrt(a), sqrt(1 - a)))


class AssessmentCreateSerializer(serializers.Serializer):
    region = serializers.PrimaryKeyRelatedField(queryset=Region.objects.all())
    patient_age_group = serializers.CharField(max_length=50)
    symptoms_list = serializers.ListField(
        child=serializers.SlugRelatedField(slug_field="slug", queryset=Symptom.objects.all()),
        allow_empty=False,
    )
    patient_latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)
    patient_longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False, allow_null=True)

    def validate(self, attrs):
        symptoms = attrs.get("symptoms_list", [])
        attrs["symptoms_list"] = list(dict.fromkeys(symptoms))
        return attrs


class EmergencySnakeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Snake
        fields = ["id", "common_name", "scientific_name", "venom_type"]


class EmergencyFacilitySerializer(HealthFacilityStockSerializer):
    class Meta(HealthFacilityStockSerializer.Meta):
        fields = HealthFacilityStockSerializer.Meta.fields


class BootstrapPayloadSerializer(serializers.Serializer):
    snakes = SnakeDetailSerializer(many=True)
    health_facilities = HealthFacilityStockSerializer(many=True)
    emergency_guides = serializers.ListField(child=serializers.DictField())
    educational_content = serializers.ListField(child=serializers.DictField())


class AssessmentResultSerializer(serializers.Serializer):
    assessment_id = serializers.IntegerField()
    risk_level = serializers.CharField()
    predicted_envenomation = serializers.CharField()
    recommended_actions = serializers.ListField(child=serializers.CharField())
    likely_snakes = serializers.ListField(child=serializers.CharField())
    nearest_facility = serializers.DictField(allow_null=True)
    severity_score = serializers.IntegerField()


class FirstAidStepSerializer(serializers.ModelSerializer):
    class Meta:
        model = FirstAidStep
        fields = [
            "id",
            "step_number",
            "title",
            "description",
            "do_statement",
            "dont_statement",
            "icon_name",
            "target_audience",
        ]


class EducationalMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = EducationalMaterial
        fields = [
            "id",
            "title",
            "category",
            "file_attachment",
            "video_url",
            "payload_body",
            "downloaded_count",
        ]