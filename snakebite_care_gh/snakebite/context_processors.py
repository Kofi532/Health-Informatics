from .views import (
	SNAKEBITE_MEMBER_TYPE_OPTIONS,
	SNAKEBITE_MEMBER_TYPE_SESSION_KEY,
	SNAKEBITE_NATIONALITY_OPTIONS,
	SNAKEBITE_NATIONALITY_SESSION_KEY,
)


_FLAG_ASSET_MAP = {
	'ghana': 'snakebite/flags/ghana.png',
	'malawi': 'snakebite/flags/malawi.png',
	'kenya': 'snakebite/flags/kenya.png',
	'nigeria': 'snakebite/flags/nigeria.png',
	'zambia': 'snakebite/flags/zambia.png',
}


def venomguard_profile(request):
	nationality_labels = dict(SNAKEBITE_NATIONALITY_OPTIONS)
	member_type_labels = dict(SNAKEBITE_MEMBER_TYPE_OPTIONS)

	nationality_code = request.session.get(SNAKEBITE_NATIONALITY_SESSION_KEY, '')
	member_type_code = request.session.get(SNAKEBITE_MEMBER_TYPE_SESSION_KEY, '')

	return {
		'venomguard_nationality_code': nationality_code,
		'venomguard_nationality_label': nationality_labels.get(nationality_code, ''),
		'venomguard_member_type_code': member_type_code,
		'venomguard_member_type_label': member_type_labels.get(member_type_code, ''),
		'venomguard_nationality_flag_path': _FLAG_ASSET_MAP.get(nationality_code, ''),
	}
