from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import PatientCase


class SnakebiteAccessAndCHWTests(TestCase):
    def test_patient_case_generates_case_id(self):
        case = PatientCase.objects.create(
            patient_name='Amina Boateng',
            patient_age=22,
            location='Takoradi',
            symptoms='Severe pain\nSwelling',
            assigned_to='CHW Team 2',
        )

        self.assertTrue(case.case_id.startswith('VG-'))
        self.assertTrue(len(case.case_id.split('-')[-1]) >= 5)

    def test_chw_home_requires_access(self):
        response = self.client.get(reverse('snakebite:chw_home'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/venomguard/access/', response.url)

    def test_chw_home_renders_for_healthcare_member(self):
        session = self.client.session
        session['snakebite_access_granted'] = True
        session['snakebite_nationality'] = 'ghana'
        session['snakebite_member_type'] = 'healthcare'
        session.save()

        response = self.client.get(reverse('snakebite:chw_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Healthcare Worker')

    def test_case_details_redirects_to_latest_available_case_when_missing(self):
        case = PatientCase.objects.create(
            patient_name='Kwame Boateng',
            patient_age=28,
            location='Accra',
            symptoms='Severe pain\nSwelling',
        )

        session = self.client.session
        session['snakebite_access_granted'] = True
        session['snakebite_nationality'] = 'ghana'
        session['snakebite_member_type'] = 'healthcare'
        session.save()

        response = self.client.get(reverse('snakebite:case_details', kwargs={'pk': 9999}))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('snakebite:case_details', kwargs={'pk': case.pk}))

    def test_case_details_renders_uploaded_photo(self):
        case = PatientCase.objects.create(
            patient_name='Akosua Boateng',
            patient_age=31,
            location='Kumasi',
            symptoms='Severe pain\nSwelling',
            photo=SimpleUploadedFile(
                'case_photo.jpg',
                b'fake-image-data',
                content_type='image/jpeg',
            ),
        )

        session = self.client.session
        session['snakebite_access_granted'] = True
        session['snakebite_nationality'] = 'ghana'
        session['snakebite_member_type'] = 'healthcare'
        session.save()

        response = self.client.get(reverse('snakebite:case_details', kwargs={'pk': case.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'case_photo.jpg')
        self.assertContains(response, 'img')

    def test_community_home_uses_valid_nav_routes(self):
        session = self.client.session
        session['snakebite_access_granted'] = True
        session['snakebite_nationality'] = 'ghana'
        session['snakebite_member_type'] = 'community'
        session.save()

        self.assertEqual(reverse('snakebite:community_home'), '/venomguard/community-home/')
        self.assertEqual(reverse('snakebite:report_sighting'), '/venomguard/report/')
        self.assertEqual(reverse('snakebite:report'), '/venomguard/report/')
        self.assertEqual(reverse('snakebite:antivenom_map'), '/venomguard/antivenom-stock-map/')
        self.assertEqual(reverse('snakebite:map'), '/venomguard/map/')
        self.assertEqual(reverse('snakebite:settings'), '/venomguard/settings/')

        response = self.client.get(reverse('snakebite:community_home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Start Bite Assessment')

        settings_response = self.client.get(reverse('snakebite:settings'))
        self.assertEqual(settings_response.status_code, 200)
        self.assertContains(settings_response, 'Settings')

    def test_report_sighting_submits_selected_bite_and_time_values(self):
        session = self.client.session
        session['snakebite_access_granted'] = True
        session['snakebite_nationality'] = 'ghana'
        session['snakebite_member_type'] = 'community'
        session.save()

        photo = SimpleUploadedFile(
            'sighting.jpg',
            b'fake-image-data',
            content_type='image/jpeg',
        )

        response = self.client.post(
            reverse('snakebite:report_sighting'),
            {
                'headline': 'Snake seen near school',
                'description': 'Large green snake by the road',
                'was_bitten': 'yes',
                'contact_number': '+233200000000',
                'time_seen': 'earlier_today',
                'photo': photo,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith('/venomguard/case-details/'))
        self.assertTrue(self.client.get(response.url).status_code == 200)
