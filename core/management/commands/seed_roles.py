from django.core.management.base import BaseCommand
from core.models import Role
from officials.models import Official

class Command(BaseCommand):
    help = 'Seed roles based on official positions'

    def handle(self, *args, **options):
        # Format: (name, display_name, permission_level)
        roles_to_create = [
            ('admin', 'Administrator', 1),
            ('captain', 'Punong Barangay (Captain)', 1),
            ('secretary', 'Barangay Secretary', 2),
            ('treasurer', 'Barangay Treasurer', 2),
            ('kagawad', 'Sangguniang Barangay Member', 2),
            ('sk_chairman', 'SK Chairperson', 2),
            ('sk_kagawad', 'SK Kagawad', 2),
            ('tanod', 'Barangay Tanod', 2),
            ('bhw', 'Barangay Health Worker', 2),
            ('nutrition_scholar', 'Barangay Nutrition Scholar', 2),
            ('day_care_worker', 'Day Care Worker', 2),
            ('lupon', 'Lupon Member', 2),
            ('clerk', 'Barangay Clerk', 2),
            ('staff', 'Barangay Staff', 2),
            ('resident', 'Resident', 3),
        ]

        for name, display_name, level in roles_to_create:
            role, created = Role.objects.update_or_create(
                name=name,
                defaults={
                    'display_name': display_name,
                    'permission_level': level
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created role: {name}'))
            else:
                self.stdout.write(f'Updated role: {name}')

        self.stdout.write(self.style.SUCCESS('Successfully seeded roles'))
