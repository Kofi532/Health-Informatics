from django.contrib import admin

from .models import (
	EducationalMaterial,
	EnvenomationType,
	FirstAidStep,
	HealthFacility,
	PatientAssessment,
	Region,
	Snake,
	Symptom,
)


admin.site.register(Region)
admin.site.register(HealthFacility)
admin.site.register(Snake)
admin.site.register(Symptom)
admin.site.register(EnvenomationType)
admin.site.register(PatientAssessment)
admin.site.register(FirstAidStep)
admin.site.register(EducationalMaterial)
