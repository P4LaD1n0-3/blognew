import os
import django
from django.test import Client
from django.contrib.auth import get_user_model

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

User = get_user_model()
admin_user = User.objects.filter(is_superuser=True).first()

if not admin_user:
    print("No superuser found.")
    exit(1)

client = Client()
client.force_login(admin_user)

# Dashboard
response = client.get('/pt-br/admin/')
with open('dashboard.html', 'wb') as f:
    f.write(response.content)

# Changelist (Groups)
response = client.get('/pt-br/admin/auth/group/')
with open('group_list.html', 'wb') as f:
    f.write(response.content)

print("HTML saved.")
