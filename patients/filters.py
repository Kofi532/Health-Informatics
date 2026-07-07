from django.db.models import Q
from rest_framework.filters import SearchFilter


class PatientSearchFilter(SearchFilter):
    search_param = 'q'

    def get_search_fields(self, view, request):
        return ['first_name', 'last_name', 'email', 'phone_number', 'address', 'emergency_contact']
