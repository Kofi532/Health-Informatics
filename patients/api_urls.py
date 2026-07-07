from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    PatientViewSet,
    EncounterViewSet,
    VitalSignViewSet,
    AppointmentViewSet,
    current_user,
)

router = DefaultRouter()
router.register(r'patients', PatientViewSet, basename='patient')
router.register(r'encounters', EncounterViewSet, basename='encounter')
router.register(r'vitals', VitalSignViewSet, basename='vitals')
router.register(r'appointments', AppointmentViewSet, basename='appointment')

urlpatterns = [
    path('', include(router.urls)),
    path('me/', current_user, name='current_user'),
]
