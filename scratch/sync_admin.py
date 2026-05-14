import os
import sys
import django

# Add the current directory to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'barangay_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from core.models import Role

User = get_user_model()

print("Syncing superuser roles...")
admin_role = Role.objects.filter(name='admin').first()
if admin_role:
    superusers = User.objects.filter(is_superuser=True, role__isnull=True)
    for user in superusers:
        print(f"Assigning 'admin' role to {user.username}...")
        user.role = admin_role
        user.save()
else:
    print("Admin role not found!")

print("Done.")
