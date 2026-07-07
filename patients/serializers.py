from rest_framework import serializers
from .models import Patient, Encounter, VitalSign, Appointment


class VitalSignSerializer(serializers.ModelSerializer):
    class Meta:
        model = VitalSign
        fields = '__all__'


class EncounterSerializer(serializers.ModelSerializer):
    vital_signs = VitalSignSerializer(many=True, read_only=True)

    class Meta:
        model = Encounter
        fields = ['id', 'patient', 'encounter_date', 'reason', 'diagnosis', 'notes', 'provider', 'vital_signs']


class AppointmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Appointment
        fields = '__all__'


class PatientSerializer(serializers.ModelSerializer):
    encounters = EncounterSerializer(many=True, read_only=True)
    appointments = AppointmentSerializer(many=True, read_only=True)

    class Meta:
        model = Patient
        fields = ['id', 'first_name', 'last_name', 'date_of_birth', 'gender', 'email', 'phone_number', 'address', 'emergency_contact', 'created_at', 'updated_at', 'encounters', 'appointments']
