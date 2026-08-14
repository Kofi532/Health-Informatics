from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView, TemplateView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='project_selector.html'), name='project_selector'),
    path('health/', include('patients.urls')),
    path('venomguard/', include(('snakebite.urls', 'snakebite'), namespace='snakebite')),
    path('snakebite/', RedirectView.as_view(pattern_name='snakebite:home', permanent=False)),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/', include('patients.api_urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
