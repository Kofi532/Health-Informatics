from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .views import AssessmentCreateView, EducationalMaterialViewSet, FirstAidStepViewSet, HealthFacilityStockViewSet, NearbyAntivenomFacilitiesView, SnakeViewSet, SyncBootstrapView


router = DefaultRouter()
router.register(r'snakes', SnakeViewSet, basename='snake')
router.register(r'health-facilities', HealthFacilityStockViewSet, basename='healthfacility')
router.register(r'first-aid-steps', FirstAidStepViewSet, basename='firstaidstep')
router.register(r'educational-materials', EducationalMaterialViewSet, basename='educationalmaterial')

app_name = 'snakebite'

urlpatterns = [
	path('access/', views.access_view, name='access'),
	path('', views.home_view, name='home'),
	path('first-aid/', views.first_aid_view, name='first_aid'),
	path('identify-symptoms/', views.identify_symptoms_view, name='identify_symptoms'),
	path('snakes-in-my-area/', views.snakes_in_area_view, name='snakes_in_area'),
	path('education-training/', views.education_training_view, name='education_training'),
	path('antivenom-stock-map/', views.antivenom_map_view, name='antivenom_map'),
	path('resources/', views.resources_view, name='resources'),
	path('api/assessments/', AssessmentCreateView.as_view(), name='assessment-create'),
	path('api/nearby-antivenom-facilities/', NearbyAntivenomFacilitiesView.as_view(), name='nearby-antivenom-facilities'),
	path('api/bootstrap/', SyncBootstrapView.as_view(), name='sync-bootstrap'),
	path('api/', include(router.urls)),
]
