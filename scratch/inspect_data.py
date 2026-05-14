import os
import sys
import django

# Add the current directory to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'barangay_project.settings')
django.setup()

from django.contrib.auth import get_user_model
from officials.models import Official

User = get_user_model()

print("Users and their roles:")
for user in User.objects.all():
    role_name = user.role.name if user.role else "None"
    print(f"- {user.username}: role={role_name}, is_superuser={user.is_superuser}")

print("\nOfficials:")
for official in Official.objects.all():
    user_name = official.user.username if official.user else "None"
    print(f"- {official.resident.full_name}: position={official.position}, user={user_name}, status={official.status}")
