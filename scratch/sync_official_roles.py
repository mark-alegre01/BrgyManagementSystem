import os
import sys
import django

# Add the current directory to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'barangay_project.settings')
django.setup()

from officials.models import Official

print("Syncing official roles...")
officials = Official.objects.all()
for official in officials:
    print(f"Syncing {official.resident.full_name} ({official.position})...")
    official.save() # This triggers the role sync logic in Official.save()

print("Done syncing official roles.")
