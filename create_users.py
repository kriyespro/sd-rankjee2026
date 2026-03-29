import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from users.models import CustomUser

def create_users():
    if not CustomUser.objects.filter(username='admin').exists():
        CustomUser.objects.create_superuser('admin', 'admin@example.com', 'AdminPassword123!')
        print("Created admin user")
    
    if not CustomUser.objects.filter(username='testuser1').exists():
        CustomUser.objects.create_user('testuser1', 'testuser1@example.com', 'TestUserPassword123!')
        print("Created testuser1")
        
    if not CustomUser.objects.filter(username='testuser2').exists():
        CustomUser.objects.create_user('testuser2', 'testuser2@example.com', 'TestUserPassword123!')
        print("Created testuser2")

if __name__ == '__main__':
    create_users()
