import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'barangay_project.settings')
django.setup()

from residents.models import Purok

center_lat = 9.4898
center_lng = 125.7222

# Small variations to scatter the points slightly around the center
# Approx 0.001 is roughly 100 meters
puroks = Purok.objects.all()
for i, p in enumerate(puroks):
    if p.latitude is None:
        p.latitude = center_lat + random.uniform(-0.003, 0.003)
        p.longitude = center_lng + random.uniform(-0.003, 0.003)
        p.save()
        print(f"Seeded {p.name}: {p.latitude}, {p.longitude}")
print("Seeding complete.")
