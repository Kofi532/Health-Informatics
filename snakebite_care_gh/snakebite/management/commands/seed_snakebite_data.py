import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from snakebite.models import (
    EducationalMaterial,
    EnvenomationType,
    FirstAidStep,
    HealthFacility,
    PatientAssessment,
    Region,
    Snake,
    Symptom,
)


class Command(BaseCommand):
    help = "Seed realistic demo data for the Snakebite app."

    def add_arguments(self, parser):
        parser.add_argument(
            "--assessments",
            type=int,
            default=30,
            help="Number of patient assessments to generate (default: 30).",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Random seed for reproducible data (default: 42).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        rng = random.Random(options["seed"])
        assessments_to_create = max(0, options["assessments"])

        regions = self._seed_regions()
        snakes = self._seed_snakes(regions)
        symptoms = self._seed_symptoms()
        envenomation_types = self._seed_envenomation_types(snakes, symptoms)
        facilities = self._seed_health_facilities(regions, rng)
        first_aid_steps = self._seed_first_aid_steps()
        materials = self._seed_educational_materials()
        assessments = self._seed_patient_assessments(
            regions,
            symptoms,
            envenomation_types,
            assessments_to_create,
            rng,
        )

        self.stdout.write(self.style.SUCCESS("Snakebite demo data seeded successfully."))
        self.stdout.write(f"Regions: {len(regions)}")
        self.stdout.write(f"Snakes: {len(snakes)}")
        self.stdout.write(f"Symptoms: {len(symptoms)}")
        self.stdout.write(f"Envenomation types: {len(envenomation_types)}")
        self.stdout.write(f"Health facilities: {len(facilities)}")
        self.stdout.write(f"First-aid steps: {len(first_aid_steps)}")
        self.stdout.write(f"Educational materials: {len(materials)}")
        self.stdout.write(f"Patient assessments created: {assessments}")

    def _seed_regions(self):
        region_payloads = [
            ("Greater Accra", "GA"),
            ("Ashanti", "AS"),
            ("Northern", "NR"),
            ("Upper East", "UE"),
            ("Volta", "VO"),
        ]

        regions = []
        for name, code in region_payloads:
            region, _ = Region.objects.get_or_create(name=name, defaults={"code": code})
            if region.code != code:
                region.code = code
                region.save(update_fields=["code"])
            regions.append(region)
        return regions

    def _seed_snakes(self, regions):
        snake_payloads = [
            {
                "common_name": "Puff Adder",
                "scientific_name": "Bitis arietans",
                "venom_type": Snake.VenomType.CYTOTOXIC,
                "description": "A heavy-bodied viper responsible for many bites in West Africa.",
                "visual_features": "Brown-yellow zigzag pattern and broad triangular head.",
                "regions": ["GA", "AS", "VO"],
            },
            {
                "common_name": "Black-necked Spitting Cobra",
                "scientific_name": "Naja nigricollis",
                "venom_type": Snake.VenomType.NEUROTOXIC,
                "description": "Known to spit venom and deliver painful defensive bites.",
                "visual_features": "Dark neck band and smooth scales.",
                "regions": ["GA", "NR", "UE"],
            },
            {
                "common_name": "West African Carpet Viper",
                "scientific_name": "Echis ocellatus",
                "venom_type": Snake.VenomType.HEMOTOXIC,
                "description": "Medically significant species associated with severe coagulopathy.",
                "visual_features": "Distinct eye-like dorsal markings with rasping scales.",
                "regions": ["NR", "UE"],
            },
            {
                "common_name": "Forest Cobra",
                "scientific_name": "Naja melanoleuca",
                "venom_type": Snake.VenomType.NEUROTOXIC,
                "description": "Large cobra found in forested and peri-urban areas.",
                "visual_features": "Glossy dark body with light throat and hood.",
                "regions": ["AS", "VO"],
            },
        ]

        code_map = {region.code: region for region in regions}
        snakes = []
        for payload in snake_payloads:
            snake, _ = Snake.objects.get_or_create(
                scientific_name=payload["scientific_name"],
                defaults={
                    "common_name": payload["common_name"],
                    "venom_type": payload["venom_type"],
                    "description": payload["description"],
                    "visual_features": payload["visual_features"],
                },
            )
            changed = False
            for field in ["common_name", "venom_type", "description", "visual_features"]:
                if getattr(snake, field) != payload[field]:
                    setattr(snake, field, payload[field])
                    changed = True
            if changed:
                snake.save()

            snake.region_distribution.set([code_map[code] for code in payload["regions"] if code in code_map])
            snakes.append(snake)

        return snakes

    def _seed_symptoms(self):
        symptom_payloads = [
            ("Localized swelling", "Rapid swelling around bite site", "Skin and Soft Tissue"),
            ("Severe pain", "Intense pain at or near bite location", "Nervous System"),
            ("Spontaneous bleeding", "Bleeding from gums, wounds, or injection sites", "Hematologic"),
            ("Ptosis", "Drooping eyelids indicating neuromuscular involvement", "Neurologic"),
            ("Difficulty breathing", "Shortness of breath or labored breathing", "Respiratory"),
            ("Nausea and vomiting", "Gastrointestinal disturbance after bite", "Gastrointestinal"),
            ("Dark urine", "Possible hemolysis or renal stress", "Renal"),
            ("Dizziness", "Lightheadedness or near-fainting episodes", "Cardiovascular"),
        ]

        symptoms = []
        for name, description, body_system in symptom_payloads:
            symptom, _ = Symptom.objects.get_or_create(
                name=name,
                defaults={
                    "description": description,
                    "body_system": body_system,
                },
            )
            changed = False
            if symptom.description != description:
                symptom.description = description
                changed = True
            if symptom.body_system != body_system:
                symptom.body_system = body_system
                changed = True
            if changed:
                symptom.save()
            symptoms.append(symptom)

        return symptoms

    def _seed_envenomation_types(self, snakes, symptoms):
        snake_by_venom = {
            Snake.VenomType.HEMOTOXIC: [],
            Snake.VenomType.NEUROTOXIC: [],
            Snake.VenomType.CYTOTOXIC: [],
        }
        for snake in snakes:
            snake_by_venom[snake.venom_type].append(snake)

        symptoms_by_name = {symptom.name: symptom for symptom in symptoms}
        payloads = [
            (
                "Hemotoxic Envenomation",
                Snake.VenomType.HEMOTOXIC,
                ["Spontaneous bleeding", "Dark urine", "Dizziness"],
            ),
            (
                "Neurotoxic Envenomation",
                Snake.VenomType.NEUROTOXIC,
                ["Ptosis", "Difficulty breathing", "Severe pain"],
            ),
            (
                "Cytotoxic Envenomation",
                Snake.VenomType.CYTOTOXIC,
                ["Localized swelling", "Severe pain", "Nausea and vomiting"],
            ),
        ]

        envenomation_types = []
        for type_name, venom_type, symptom_names in payloads:
            etype, _ = EnvenomationType.objects.get_or_create(type_name=type_name)
            etype.target_snakes.set(snake_by_venom.get(venom_type, []))
            etype.associated_symptoms.set(
                [symptoms_by_name[name] for name in symptom_names if name in symptoms_by_name]
            )
            envenomation_types.append(etype)

        return envenomation_types

    def _seed_health_facilities(self, regions, rng):
        facility_types = [
            HealthFacility.FacilityType.DISTRICT_HOSPITAL,
            HealthFacility.FacilityType.HEALTH_CENTER,
            HealthFacility.FacilityType.CHPS,
        ]

        region_centers = {
            "GA": (5.603700, -0.187000),
            "AS": (6.688500, -1.624400),
            "NR": (9.400800, -0.839300),
            "UE": (10.785600, -0.851400),
            "VO": (6.600800, 0.471300),
        }

        facilities = []
        for region in regions:
            base_lat, base_lon = region_centers.get(region.code, (7.0, -1.0))
            for idx, facility_type in enumerate(facility_types, start=1):
                name = f"{region.name} {facility_type.replace('_', ' ').title()} {idx}"
                antivenom_available = facility_type != HealthFacility.FacilityType.CHPS or rng.choice([True, False])
                antivenom_cost = round(rng.uniform(180.0, 1200.0), 2) if antivenom_available else None
                stock_days_ago = rng.randint(0, 30)

                facility, _ = HealthFacility.objects.get_or_create(
                    name=name,
                    region=region,
                    defaults={
                        "facility_type": facility_type,
                        "latitude": round(base_lat + rng.uniform(-0.25, 0.25), 6),
                        "longitude": round(base_lon + rng.uniform(-0.25, 0.25), 6),
                        "contact_number": f"+23320{rng.randint(1000000, 9999999)}",
                        "antivenom_available": antivenom_available,
                        "antivenom_cost": antivenom_cost,
                        "last_stock_update": timezone.now() - timedelta(days=stock_days_ago),
                    },
                )

                facility.facility_type = facility_type
                facility.antivenom_available = antivenom_available
                facility.antivenom_cost = antivenom_cost
                facility.last_stock_update = timezone.now() - timedelta(days=stock_days_ago)
                if not facility.contact_number:
                    facility.contact_number = f"+23320{rng.randint(1000000, 9999999)}"
                if facility.latitude is None:
                    facility.latitude = round(base_lat + rng.uniform(-0.25, 0.25), 6)
                if facility.longitude is None:
                    facility.longitude = round(base_lon + rng.uniform(-0.25, 0.25), 6)
                facility.save()

                facilities.append(facility)

        return facilities

    def _seed_first_aid_steps(self):
        steps = [
            (
                1,
                "Move to Safety",
                "Ensure patient and responder are away from snake strike zone.",
                "Move patient to a safe area and keep them calm.",
                "Do not attempt to catch or kill the snake.",
                "shield-check",
                FirstAidStep.TargetAudience.FIRST_RESPONDER,
            ),
            (
                2,
                "Immobilize Limb",
                "Limit venom spread by reducing movement.",
                "Immobilize the bitten limb with a splint at heart level.",
                "Do not apply a tight tourniquet.",
                "bandage",
                FirstAidStep.TargetAudience.FIRST_RESPONDER,
            ),
            (
                3,
                "Rapid Referral",
                "Transfer to equipped facility for antivenom and monitoring.",
                "Arrange immediate transport and pre-notify receiving facility.",
                "Do not delay referral while trying home treatments.",
                "ambulance",
                FirstAidStep.TargetAudience.HEALTH_WORKER,
            ),
        ]

        objects = []
        for step in steps:
            step_obj, _ = FirstAidStep.objects.get_or_create(
                step_number=step[0],
                target_audience=step[6],
                defaults={
                    "title": step[1],
                    "description": step[2],
                    "do_statement": step[3],
                    "dont_statement": step[4],
                    "icon_name": step[5],
                },
            )
            step_obj.title = step[1]
            step_obj.description = step[2]
            step_obj.do_statement = step[3]
            step_obj.dont_statement = step[4]
            step_obj.icon_name = step[5]
            step_obj.save()
            objects.append(step_obj)

        return objects

    def _seed_educational_materials(self):
        materials_payload = [
            (
                "National Snakebite First Response Guide",
                EducationalMaterial.Category.GUIDELINE,
                "https://example.org/snakebite-guideline",
                "Step-by-step guidance for first contact and referral.",
            ),
            (
                "How to Use Pressure Immobilization",
                EducationalMaterial.Category.TRAINING,
                "https://example.org/pressure-immobilization-video",
                "A practical tutorial for frontline responders.",
            ),
            (
                "Community Snakebite Awareness Poster",
                EducationalMaterial.Category.POSTER,
                "",
                "Printable poster for schools and community centers.",
            ),
            (
                "Recognizing Dangerous Snake Species",
                EducationalMaterial.Category.VIDEO,
                "https://example.org/ghana-snakes-overview",
                "Video overview of common venomous snakes in Ghana.",
            ),
        ]

        materials = []
        for title, category, video_url, payload_body in materials_payload:
            material, _ = EducationalMaterial.objects.get_or_create(
                title=title,
                defaults={
                    "category": category,
                    "video_url": video_url,
                    "payload_body": payload_body,
                    "downloaded_count": 0,
                },
            )
            material.category = category
            material.video_url = video_url
            material.payload_body = payload_body
            material.save()
            materials.append(material)

        return materials

    def _seed_patient_assessments(self, regions, symptoms, envenomation_types, total, rng):
        age_groups = ["0-5", "6-12", "13-17", "18-35", "36-60", "60+"]
        actions = [
            "Observe for progression and review after 2 hours.",
            "Refer to nearest antivenom-capable facility today.",
            "Urgent transfer and monitor airway, breathing, circulation.",
        ]

        created = 0
        for _ in range(total):
            region = rng.choice(regions)
            predicted = rng.choice(envenomation_types + [None])
            assessment = PatientAssessment.objects.create(
                region=region,
                patient_age_group=rng.choice(age_groups),
                predicted_envenomation=predicted,
                recommended_action=rng.choice(actions),
            )

            max_symptoms = min(5, len(symptoms))
            count = rng.randint(1, max_symptoms) if max_symptoms else 0
            if count:
                picked = rng.sample(symptoms, count)
                assessment.symptoms_present.set(picked)
            created += 1

        return created
