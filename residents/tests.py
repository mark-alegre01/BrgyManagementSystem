from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from core.models import Role, UserProfile
from residents.models import Household, Purok

User = get_user_model()

class HouseholdMapTestCase(TestCase):
    def setUp(self):
        # Create roles
        self.admin_role, _ = Role.objects.get_or_create(name='admin', defaults={'display_name': 'Admin', 'permission_level': 1})
        self.resident_role, _ = Role.objects.get_or_create(name='resident', defaults={'display_name': 'Resident', 'permission_level': 3})
        
        # Create users
        self.admin_user = User.objects.create_user(username='admin_test_user', password='password', role=self.admin_role)
        self.resident_user = User.objects.create_user(username='resident_test_user', password='password', role=self.resident_role)
        
        # Create profiles
        UserProfile.objects.create(user=self.admin_user)
        UserProfile.objects.create(user=self.resident_user)
        
        # Create Purok
        self.purok = Purok.objects.create(name='Purok Test 1', latitude=9.4898, longitude=125.7222)
        
        # Create Household
        self.household = Household.objects.create(
            household_no='HH-TEST-01',
            address='123 Test St',
            purok=self.purok,
            latitude=9.4895,
            longitude=125.7225
        )

    def test_household_map_api(self):
        self.client.login(username='admin_test_user', password='password')
        response = self.client.get(reverse('residents:household_map_api'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['type'], 'FeatureCollection')
        self.assertTrue(len(data['features']) > 0)
        feature = data['features'][0]
        self.assertEqual(feature['geometry']['coordinates'], [125.7225, 9.4895])
        self.assertEqual(feature['properties']['head'], 'Not Assigned')
        self.assertNotIn('address', feature['properties'])

    def test_household_add_saves_coordinates(self):
        self.client.login(username='admin_test_user', password='password')
        response = self.client.post(reverse('residents:household_add'), {
            'household_no': 'HH-NEW-02',
            'address': '456 New St',
            'purok': self.purok.id,
            'latitude': '9.4900',
            'longitude': '125.7220'
        })
        self.assertRedirects(response, reverse('residents:household_list'))
        new_hh = Household.objects.get(household_no='HH-NEW-02')
        self.assertEqual(new_hh.latitude, 9.4900)
        self.assertEqual(new_hh.longitude, 125.7220)

    def test_household_edit_saves_coordinates(self):
        self.client.login(username='admin_test_user', password='password')
        response = self.client.post(reverse('residents:household_edit', args=[self.household.pk]), {
            'household_no': 'HH-TEST-01-MOD',
            'address': '123 Test St Mod',
            'purok': self.purok.id,
            'latitude': '9.4890',
            'longitude': '125.7230'
        })
        self.assertRedirects(response, reverse('residents:household_list'))
        self.household.refresh_from_db()
        self.assertEqual(self.household.household_no, 'HH-TEST-01-MOD')
        self.assertEqual(self.household.latitude, 9.4890)
        self.assertEqual(self.household.longitude, 125.7230)
