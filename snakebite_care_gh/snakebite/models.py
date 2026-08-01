from django.db import models
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from django.utils.text import slugify


class Region(models.Model):
	name = models.CharField(max_length=120, unique=True)
	code = models.CharField(max_length=20, unique=True)

	class Meta:
		ordering = ["name"]
		indexes = [
			models.Index(fields=["name"]),
			models.Index(fields=["code"]),
		]

	def __str__(self):
		return self.name


class HealthFacility(models.Model):
	class FacilityType(models.TextChoices):
		DISTRICT_HOSPITAL = "district_hospital", "District Hospital"
		HEALTH_CENTER = "health_center", "Health Center"
		CHPS = "chps", "CHPS"

	name = models.CharField(max_length=150)
	facility_type = models.CharField(max_length=30, choices=FacilityType.choices)
	region = models.ForeignKey(
		Region,
		on_delete=models.PROTECT,
		related_name="health_facilities",
	)
	latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
	longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
	contact_number = models.CharField(max_length=30, blank=True)
	antivenom_available = models.BooleanField(default=False)
	antivenom_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
	last_stock_update = models.DateTimeField(null=True, blank=True)

	class Meta:
		ordering = ["name"]
		indexes = [
			models.Index(fields=["facility_type"]),
			models.Index(fields=["region"]),
			models.Index(fields=["antivenom_available"]),
			models.Index(fields=["last_stock_update"]),
		]

	def __str__(self):
		return f"{self.name} ({self.get_facility_type_display()})"


class Snake(models.Model):
	class VenomType(models.TextChoices):
		HEMOTOXIC = "hemotoxic", "Hemotoxic"
		NEUROTOXIC = "neurotoxic", "Neurotoxic"
		CYTOTOXIC = "cytotoxic", "Cytotoxic"

	common_name = models.CharField(max_length=150)
	scientific_name = models.CharField(max_length=150)
	venom_type = models.CharField(max_length=20, choices=VenomType.choices)
	region_distribution = models.ManyToManyField(Region, related_name="snakes", blank=True)
	description = models.TextField(blank=True)
	visual_features = models.TextField(blank=True)
	image = models.ImageField(upload_to="snakes/", blank=True, null=True)

	class Meta:
		ordering = ["common_name"]
		indexes = [
			models.Index(fields=["common_name"]),
			models.Index(fields=["scientific_name"]),
			models.Index(fields=["venom_type"]),
		]

	def __str__(self):
		return self.common_name


class Symptom(models.Model):
	name = models.CharField(max_length=150, unique=True)
	slug = models.SlugField(max_length=170, unique=True, blank=True)
	description = models.TextField(blank=True)
	body_system = models.CharField(max_length=120)

	class Meta:
		ordering = ["name"]
		indexes = [
			models.Index(fields=["slug"]),
			models.Index(fields=["body_system"]),
		]

	def save(self, *args, **kwargs):
		if not self.slug:
			self.slug = slugify(self.name)
		super().save(*args, **kwargs)

	def __str__(self):
		return self.name


class EnvenomationType(models.Model):
	type_name = models.CharField(max_length=120, unique=True)
	target_snakes = models.ManyToManyField(Snake, related_name="envenomation_types", blank=True)
	associated_symptoms = models.ManyToManyField(Symptom, related_name="envenomation_types", blank=True)

	class Meta:
		ordering = ["type_name"]
		indexes = [
			models.Index(fields=["type_name"]),
		]

	def __str__(self):
		return self.type_name


class PatientAssessment(models.Model):
	class RiskLevel(models.TextChoices):
		LOW = "low", "Low"
		MEDIUM = "medium", "Medium"
		HIGH = "high", "High"

	timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
	region = models.ForeignKey(
		Region,
		on_delete=models.PROTECT,
		related_name="patient_assessments",
	)
	patient_age_group = models.CharField(max_length=50)
	symptoms_present = models.ManyToManyField(Symptom, related_name="patient_assessments", blank=True)
	severity_score = models.PositiveSmallIntegerField(default=0, editable=False)
	predicted_envenomation = models.ForeignKey(
		EnvenomationType,
		on_delete=models.SET_NULL,
		null=True,
		blank=True,
		related_name="patient_assessments",
	)
	risk_level = models.CharField(max_length=10, choices=RiskLevel.choices, default=RiskLevel.LOW)
	recommended_action = models.TextField(blank=True)

	class Meta:
		ordering = ["-timestamp"]
		indexes = [
			models.Index(fields=["timestamp"]),
			models.Index(fields=["region"]),
			models.Index(fields=["patient_age_group"]),
			models.Index(fields=["risk_level"]),
			models.Index(fields=["severity_score"]),
		]

	def __str__(self):
		return f"Assessment #{self.pk or 'new'} - {self.region}"

	@classmethod
	def calculate_risk_level(cls, severity_score):
		if severity_score >= 40:
			return cls.RiskLevel.HIGH
		if severity_score >= 20:
			return cls.RiskLevel.MEDIUM
		return cls.RiskLevel.LOW

	def calculate_severity_score(self):
		symptom_count = self.symptoms_present.count() if self.pk else 0
		severity_score = symptom_count * 10
		if self.predicted_envenomation_id:
			severity_score += 15
		return severity_score

	def sync_scores(self):
		if not self.pk:
			return

		severity_score = self.calculate_severity_score()
		risk_level = self.calculate_risk_level(severity_score)
		updates = {}

		if self.severity_score != severity_score:
			updates["severity_score"] = severity_score
		if self.risk_level != risk_level:
			updates["risk_level"] = risk_level

		if updates:
			type(self).objects.filter(pk=self.pk).update(**updates)
			self.severity_score = severity_score
			self.risk_level = risk_level

	def save(self, *args, **kwargs):
		super().save(*args, **kwargs)
		self.sync_scores()


@receiver(m2m_changed, sender=PatientAssessment.symptoms_present.through)
def update_patient_assessment_scores(sender, instance, action, **kwargs):
	if action in {"post_add", "post_remove", "post_clear"}:
		instance.sync_scores()


class FirstAidStep(models.Model):
	class TargetAudience(models.TextChoices):
		FIRST_RESPONDER = "first_responder", "First Responder"
		HEALTH_WORKER = "health_worker", "Health Worker"

	step_number = models.PositiveSmallIntegerField()
	title = models.CharField(max_length=150)
	description = models.TextField(blank=True)
	do_statement = models.TextField()
	dont_statement = models.TextField()
	icon_name = models.CharField(max_length=80, blank=True)
	target_audience = models.CharField(max_length=30, choices=TargetAudience.choices)

	class Meta:
		ordering = ["step_number"]
		indexes = [
			models.Index(fields=["step_number"]),
			models.Index(fields=["target_audience"]),
		]

	def __str__(self):
		return f"Step {self.step_number}: {self.title}"


class EducationalMaterial(models.Model):
	class Category(models.TextChoices):
		GUIDELINE = "guideline", "Guideline"
		POSTER = "poster", "Poster"
		VIDEO = "video", "Video"
		TRAINING = "training", "Training"

	title = models.CharField(max_length=180)
	category = models.CharField(max_length=20, choices=Category.choices)
	file_attachment = models.FileField(upload_to="education/files/", null=True, blank=True)
	video_url = models.URLField(blank=True)
	payload_body = models.TextField(blank=True)
	downloaded_count = models.PositiveIntegerField(default=0)

	class Meta:
		ordering = ["category", "title"]
		indexes = [
			models.Index(fields=["category"]),
			models.Index(fields=["downloaded_count"]),
		]

	def __str__(self):
		return self.title
