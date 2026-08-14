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
	path('community-home/', views.community_home_view, name='community_home'),
	path('community-bite-assessment/', views.community_bite_assessment_view, name='community_bite_assessment'),
	path('community-risk-result/', views.community_risk_result_view, name='community_risk_result'),
	path('community-nearest-help/', views.community_nearest_help_view, name='community_nearest_help'),
	path('chw-home/', views.CHWHomeView.as_view(), name='chw_home'),
	path('report/', views.report_sighting_view, name='report_sighting'),
	path('report/', views.report_sighting_view, name='report'),
	path('case-details/<int:pk>/', views.CaseDetailsView.as_view(), name='case_details'),
	path('case/<int:pk>/send-referral/', views.SendReferralView.as_view(), name='send_referral'),
	path('dashboard/', views.CHWDashboardView.as_view(), name='chw_dashboard'),
	path('dashboard/<slug:metric>/', views.case_metric_list_view, name='case_metric_list'),
	path('first-aid/', views.first_aid_view, name='first_aid'),
	path('identify-symptoms/', views.identify_symptoms_view, name='identify_symptoms'),
	path('snakes-in-my-area/', views.snakes_in_area_view, name='snakes_in_area'),
	path('education-training/', views.education_training_view, name='education_training'),
	path('antivenom-stock-map/', views.antivenom_map_view, name='antivenom_map'),
	path('map/', views.antivenom_map_view, name='map'),
	path('settings/', views.settings_view, name='settings'),
	path('resources/', views.resources_view, name='resources'),
	path('api/assessments/', AssessmentCreateView.as_view(), name='assessment-create'),
	path('api/nearby-antivenom-facilities/', NearbyAntivenomFacilitiesView.as_view(), name='nearby-antivenom-facilities'),
	path('api/bootstrap/', SyncBootstrapView.as_view(), name='sync-bootstrap'),
	path('api/', include(router.urls)),
]
