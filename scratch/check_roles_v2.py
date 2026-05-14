import os
import sys
import django

# Add the current directory to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'barangay_project.settings')
django.setup()

from core.models import Role

print("Roles in database:")
roles = Role.objects.all()
for role in roles:
    print(f"- {role.name} (level: {role.permission_level})")

if not roles.exists():
    print("No roles found!")
