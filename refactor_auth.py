import os
import re

directory = '/home/mharkd/.gemini/antigravity/scratch/BrgyManagementSystem'

for root, _, files in os.walk(directory):
    if 'venv' in root or '.git' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            with open(filepath, 'r') as f:
                content = f.read()

            new_content = content

            # Handle core/models.py missing import
            if filepath.endswith('core/models.py'):
                if 'from django.conf import settings' not in new_content:
                    new_content = new_content.replace('from django.contrib.auth.models import AbstractUser', 'from django.contrib.auth.models import AbstractUser\nfrom django.conf import settings')

            # Replace imports
            if 'from django.contrib.auth import get_user_model
User = get_user_model()' in new_content:
                if 'models.py' in file:
                    new_content = new_content.replace('from django.contrib.auth import get_user_model
User = get_user_model()', 'from django.conf import settings')
                else:
                    new_content = new_content.replace('from django.contrib.auth import get_user_model
User = get_user_model()', 'from django.contrib.auth import get_user_model\nUser = get_user_model()')

            # Fix models.ForeignKey and OneToOneField
            if 'models.py' in file:
                new_content = re.sub(r'models\.ForeignKey\(\s*User\s*,', r'models.ForeignKey(settings.AUTH_USER_MODEL,', new_content)
                new_content = re.sub(r"models\.ForeignKey\(\s*['\"]auth\.User['\"]", r"models.ForeignKey(settings.AUTH_USER_MODEL", new_content)
                new_content = re.sub(r'models\.OneToOneField\(\s*User\s*,', r'models.OneToOneField(settings.AUTH_USER_MODEL,', new_content)

            if new_content != content:
                with open(filepath, 'w') as f:
                    f.write(new_content)
                print(f"Updated {filepath}")
