# Management command to create initial users
# core/management/commands/create_initial_users.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import SystemSetting, GroupRate
from datetime import date

User = get_user_model()

class Command(BaseCommand):
    help = 'Create initial users and data for church management system'
    
    def handle(self, *args, **kwargs):
        # Create admin user
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser(
                username='admin',
                email='admin@church.com',
                password='Admin123!',  # Change this immediately!
                first_name='System',
                last_name='Admin',
                role='admin'
            )
            self.stdout.write(self.style.SUCCESS('Created admin user'))
        
        # Create priest user
        if not User.objects.filter(username='priest').exists():
            priest = User.objects.create_user(
                username='priest',
                email='priest@church.com',
                password='Priest123!',  # Change this immediately!
                first_name='Father',
                last_name='Michael',
                role='priest'
            )
            self.stdout.write(self.style.SUCCESS('Created priest user'))
        
        # Create secretary user
        if not User.objects.filter(username='secretary').exists():
            User.objects.create_user(
                username='secretary',
                email='secretary@church.com',
                password='Secretary123!',  # Change this immediately!
                first_name='Mary',
                last_name='Johnson',
                role='secretary'
            )
            self.stdout.write(self.style.SUCCESS('Created secretary user'))
        
        # Seed initial settings and rates (same as before)
        settings_data = [
            {
                'key': 'validate_contribution_amount',
                'value': 'true',
                'setting_type': 'boolean',
                'description': 'Validate contribution amounts against current group rates'
            },
            {
                'key': 'validate_intention_amount',
                'value': 'true',
                'setting_type': 'boolean',
                'description': 'Validate mass intention amounts'
            },
            {
                'key': 'regular_intention_price',
                'value': '500',
                'setting_type': 'integer',
                'description': 'Price for regular mass intention (per day)'
            },
            {
                'key': 'thanksgiving_intention_price',
                'value': '3000',
                'setting_type': 'integer',
                'description': 'Minimum price for thanksgiving offering'
            },
            {
                'key': 'default_mass_days',
                'value': '[6]',  # JSON list: 0=Monday, 6=Sunday
                'setting_type': 'string',
                'description': 'Default mass days as JSON array. 0=Monday, 6=Sunday. E.g., [6] for Sunday only, [3,6] for Thursday and Sunday'
            }
        ]
        for setting in settings_data:
            SystemSetting.objects.get_or_create(
                key=setting['key'],
                defaults=setting
            )
        
        rates_data = [
            {'group_name': 'men', 'annual_amount': 1000, 'effective_from': date(2024, 1, 1)},
            {'group_name': 'women', 'annual_amount': 500, 'effective_from': date(2024, 1, 1)},
            {'group_name': 'youth', 'annual_amount': 300, 'effective_from': date(2024, 1, 1)},
            {'group_name': 'children', 'annual_amount': 200, 'effective_from': date(2024, 1, 1)},
        ]
        
        for rate in rates_data:
            GroupRate.objects.get_or_create(
                group_name=rate['group_name'],
                effective_from=rate['effective_from'],
                defaults=rate
            )
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded all initial data'))