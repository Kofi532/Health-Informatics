from rest_framework import permissions


class IsStaffOrPatientOwner(permissions.BasePermission):
    """Allow access if user is staff, or the user is linked to the patient record.

    This is intended for viewsets where the primary model is Patient or is
    related to Patient (Encounter, Appointment, VitalSign via Encounter).
    """

    def has_permission(self, request, view):
        # Require authentication (settings default) — this is extra guard
        if not request.user or not request.user.is_authenticated:
            return False
        # Staff can access
        if request.user.is_staff or request.user.is_superuser:
            return True
        # Allow any authenticated user to browse the patient directory
        if getattr(view, 'basename', None) == 'patient' and request.method in permissions.SAFE_METHODS:
            return True
        # Non-staff: allow modify/detail only if user has a linked profile
        return hasattr(request.user, 'userprofile') and request.user.userprofile.patient is not None

    def has_object_permission(self, request, view, obj):
        if request.user.is_staff or request.user.is_superuser:
            return True

        if getattr(view, 'basename', None) == 'patient' and request.method in permissions.SAFE_METHODS:
            return True

        # If the object is a Patient instance
        try:
            user_patient = request.user.userprofile.patient
        except Exception:
            return False

        if hasattr(obj, 'patient'):
            # obj is Encounter, Appointment, or VitalSign via Encounter
            if getattr(obj, 'patient', None) is not None:
                return obj.patient == user_patient
            # for VitalSign, obj.encounter.patient
            if hasattr(obj, 'encounter') and obj.encounter is not None:
                return obj.encounter.patient == user_patient

        # obj might be Patient
        if hasattr(obj, 'id'):
            return obj == user_patient

        return False
