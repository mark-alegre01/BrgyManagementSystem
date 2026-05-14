import os
import sys
import django

# Add the current directory to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'barangay_project.settings')
django.setup()

from core.models import Role

role = Role.objects.get(name='captain')
print(f"Role 'captain' level: {role.permission_level}")
