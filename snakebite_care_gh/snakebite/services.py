from decimal import Decimal
from typing import Dict, Iterable, List, Set

from .models import HealthFacility, Snake


class SnakebiteRiskEngine:
    NEUROTOXIC_MARKERS = {
        "ptosis",
        "difficulty-breathing",
        "respiratory-distress",
        "muscle-weakness",
        "weakness",
        "drooping-eyelids",
    }
    HEMOTOXIC_MARKERS = {
        "bleeding-gums",
        "dark-urine",
        "systemic-swelling",
        "swelling",
        "abnormal-bleeding",
        "bruising",
    }

    ACTION_FIRST_AID = "Start First Aid / Splint Limb"
    ACTION_AVOID_WOUND_MANIPULATION = "Do NOT cut or suck wound"
    ACTION_ANTIVENOM = "Stabilize Patient & Administer Antivenom"
    ACTION_REFERRAL = "Urgent Referral to nearest facility"

    SYMPTOM_SEVERITY_WEIGHTS = {
        "ptosis": 18,
        "difficulty-breathing": 20,
        "respiratory-distress": 20,
        "muscle-weakness": 16,
        "weakness": 10,
        "drooping-eyelids": 12,
        "bleeding-gums": 18,
        "dark-urine": 18,
        "systemic-swelling": 14,
        "swelling": 10,
        "abnormal-bleeding": 16,
        "bruising": 10,
    }

    def assess_risk(self, symptoms_list: Iterable[str]) -> Dict[str, object]:
        normalized_symptoms = self._normalize_symptoms(symptoms_list)

        neurotoxic_hits = normalized_symptoms & self.NEUROTOXIC_MARKERS
        hemotoxic_hits = normalized_symptoms & self.HEMOTOXIC_MARKERS

        severity_score = self._calculate_severity_score(normalized_symptoms)

        if neurotoxic_hits and not hemotoxic_hits:
            risk_level = "HIGH RISK"
            predicted_envenomation = "Neurotoxic"
            likely_snakes = self._snakes_for_venom_type(Snake.VenomType.NEUROTOXIC)
        elif hemotoxic_hits and not neurotoxic_hits:
            risk_level = "HIGH RISK"
            predicted_envenomation = "Hemotoxic"
            likely_snakes = self._snakes_for_venom_type(Snake.VenomType.HEMOTOXIC)
        elif neurotoxic_hits and hemotoxic_hits:
            risk_level = "HIGH RISK"
            predicted_envenomation = "Uncertain"
            likely_snakes = self._snakes_for_venom_type(
                Snake.VenomType.NEUROTOXIC,
                Snake.VenomType.HEMOTOXIC,
            )
        elif severity_score >= 40:
            risk_level = "HIGH RISK"
            predicted_envenomation = self._infer_envenomation_from_score(severity_score)
            likely_snakes = self._snakes_for_prediction(predicted_envenomation)
        elif severity_score >= 20:
            risk_level = "MEDIUM RISK"
            predicted_envenomation = self._infer_envenomation_from_score(severity_score)
            likely_snakes = self._snakes_for_prediction(predicted_envenomation)
        else:
            risk_level = "LOW RISK"
            predicted_envenomation = "Uncertain"
            likely_snakes = self._snakes_for_venom_type(
                Snake.VenomType.NEUROTOXIC,
                Snake.VenomType.HEMOTOXIC,
                Snake.VenomType.CYTOTOXIC,
            )

        return {
            "risk_level": risk_level,
            "predicted_envenomation": predicted_envenomation,
            "recommended_actions": self._recommended_actions(risk_level),
            "likely_snakes": likely_snakes,
            "severity_score": severity_score,
        }

    def _normalize_symptoms(self, symptoms_list: Iterable[str]) -> Set[str]:
        return {str(symptom).strip().lower() for symptom in symptoms_list if str(symptom).strip()}

    def _calculate_severity_score(self, symptoms: Set[str]) -> int:
        severity_score = 0

        for symptom in symptoms:
            severity_score += self.SYMPTOM_SEVERITY_WEIGHTS.get(symptom, 4)

        if symptoms & self.NEUROTOXIC_MARKERS:
            severity_score += 20
        if symptoms & self.HEMOTOXIC_MARKERS:
            severity_score += 20

        if symptoms & self.NEUROTOXIC_MARKERS and symptoms & self.HEMOTOXIC_MARKERS:
            severity_score += 10

        if len(symptoms) >= 4:
            severity_score += 10

        return severity_score

    def _infer_envenomation_from_score(self, severity_score: int) -> str:
        if severity_score >= 40:
            return "Uncertain"
        if severity_score >= 20:
            return "Uncertain"
        return "Uncertain"

    def _recommended_actions(self, risk_level: str) -> List[str]:
        actions = [self.ACTION_FIRST_AID, self.ACTION_AVOID_WOUND_MANIPULATION]
        if risk_level in {"MEDIUM RISK", "HIGH RISK"}:
            actions.append(self.ACTION_REFERRAL)
        if risk_level == "HIGH RISK":
            actions.insert(2, self.ACTION_ANTIVENOM)
        return actions

    def _snakes_for_prediction(self, predicted_envenomation: str) -> List[str]:
        if predicted_envenomation == "Neurotoxic":
            return self._snakes_for_venom_type(Snake.VenomType.NEUROTOXIC)
        if predicted_envenomation == "Hemotoxic":
            return self._snakes_for_venom_type(Snake.VenomType.HEMOTOXIC)
        return self._snakes_for_venom_type(
            Snake.VenomType.NEUROTOXIC,
            Snake.VenomType.HEMOTOXIC,
            Snake.VenomType.CYTOTOXIC,
        )

    def _snakes_for_venom_type(self, *venom_types: str) -> List[str]:
        return list(
            Snake.objects.filter(venom_type__in=venom_types)
            .order_by("common_name")
            .values_list("common_name", flat=True)
        )


def get_nearby_antivenom_facilities(latitude, longitude, max_distance_km=50, region_id=None):
    try:
        patient_latitude = Decimal(str(latitude))
        patient_longitude = Decimal(str(longitude))
        max_distance_km = float(max_distance_km)
    except (TypeError, ValueError, ArithmeticError):
        return []

    facilities = HealthFacility.objects.select_related("region").filter(antivenom_available=True)
    if region_id:
        facilities = facilities.filter(region_id=region_id)

    nearby_facilities = []
    for facility in facilities:
        if facility.latitude is None or facility.longitude is None:
            continue

        distance_km = _haversine_distance_km(
            patient_latitude,
            patient_longitude,
            facility.latitude,
            facility.longitude,
        )

        if distance_km <= max_distance_km:
            nearby_facilities.append(
                {
                    "facility_name": facility.name,
                    "facility_type": facility.get_facility_type_display(),
                    "region": {
                        "id": facility.region_id,
                        "name": facility.region.name,
                        "code": facility.region.code,
                    },
                    "antivenom_cost_ghs": f"GHS {facility.antivenom_cost:.2f}" if facility.antivenom_cost is not None else None,
                    "contact_phone": facility.contact_number,
                    "distance_km": round(distance_km, 2),
                }
            )

    nearby_facilities.sort(key=lambda item: item["distance_km"])
    return nearby_facilities


def _haversine_distance_km(latitude_1, longitude_1, latitude_2, longitude_2):
    from math import atan2, cos, radians, sin, sqrt

    earth_radius_km = 6371.0
    latitude_delta = radians(float(latitude_2 - latitude_1))
    longitude_delta = radians(float(longitude_2 - longitude_1))
    latitude_1_rad = radians(float(latitude_1))
    latitude_2_rad = radians(float(latitude_2))

    a = sin(latitude_delta / 2) ** 2 + cos(latitude_1_rad) * cos(latitude_2_rad) * sin(longitude_delta / 2) ** 2
    return 2 * earth_radius_km * atan2(sqrt(a), sqrt(1 - a))