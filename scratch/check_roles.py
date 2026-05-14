import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'barangay_project.settings')
django.setup()

from core.models import Role

print("Roles in database:")
for role in Role.objects.all():
    print(f"- {role.name} (level: {role.permission_level})")

if not Role.objects.exists():
    print("No roles found!")
