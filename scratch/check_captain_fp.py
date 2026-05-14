import os
import sys
import django

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'barangay_project.settings')
django.setup()

from officials.models import Official
from residents.models import Resident

def check_captain_fingerprint():
    captain = Official.objects.filter(position='captain', status='active').first()
    if not captain:
        print("Captain not found or not active.")
        return

    print(f"Captain: {captain.full_name}")
    print(f"Official ID: {captain.id}")
    print(f"Resident ID: {captain.resident.id}")
    print(f"Fingerprint ID: {captain.resident.fingerprint_id}")
    print(f"Fingerprint Template (first 20 chars): {str(captain.resident.fingerprint_template)[:20]}")
    print(f"Fingerprint Template Length: {len(captain.resident.fingerprint_template) if captain.resident.fingerprint_template else 0}")
    print(f"Property Access: {captain.fingerprint_template}")

if __name__ == "__main__":
    check_captain_fingerprint()
