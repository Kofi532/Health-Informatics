from rest_framework import viewsets, filters
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Patient, Encounter, VitalSign, Appointment
from .serializers import PatientSerializer, EncounterSerializer, VitalSignSerializer, AppointmentSerializer
from .permissions import IsStaffOrPatientOwner
from .filters import PatientSearchFilter
from .pagination import PatientDirectoryPagination


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    user = request.user
    return Response({
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
    })


class PatientViewSet(viewsets.ModelViewSet):
    serializer_class = PatientSerializer
    permission_classes = [IsStaffOrPatientOwner]
    filter_backends = [PatientSearchFilter, filters.OrderingFilter]
    ordering_fields = ['first_name', 'last_name', 'date_of_birth', 'created_at']
    ordering = ['last_name', 'first_name']
    pagination_class = PatientDirectoryPagination

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Patient.objects.all()
        # non-staff users only see their linked patient record
        try:
            patient = user.userprofile.patient
            return Patient.objects.filter(pk=patient.pk)
        except Exception:
            return Patient.objects.none()


class EncounterViewSet(viewsets.ModelViewSet):
    serializer_class = EncounterSerializer
    permission_classes = [IsStaffOrPatientOwner]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Encounter.objects.all()
        try:
            patient = user.userprofile.patient
            return Encounter.objects.filter(patient=patient)
        except Exception:
            return Encounter.objects.none()


class VitalSignViewSet(viewsets.ModelViewSet):
    serializer_class = VitalSignSerializer
    permission_classes = [IsStaffOrPatientOwner]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return VitalSign.objects.all()
        try:
            patient = user.userprofile.patient
            return VitalSign.objects.filter(encounter__patient=patient)
        except Exception:
            return VitalSign.objects.none()


class AppointmentViewSet(viewsets.ModelViewSet):
    serializer_class = AppointmentSerializer
    permission_classes = [IsStaffOrPatientOwner]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Appointment.objects.all()
        try:
            patient = user.userprofile.patient
            return Appointment.objects.filter(patient=patient)
        except Exception:
            return Appointment.objects.none()
