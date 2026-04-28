# core/management/commands/seed_initial_data.py
from django.core.management.base import BaseCommand
from core.models import SystemSetting, GroupRate
from datetime import date

class Command(BaseCommand):
    help = 'Seed initial data for church management system'
    
    def handle(self, *args, **kwargs):
        # Initialize system settings
        settings_data = [
            {
                'key': 'validate_contribution_amount',
                'value': 'true',
                'setting_type': 'boolean',
                'description': 'Validate contribution amounts against current rates'
            },
            {
                'key': 'validate_intention_amount',
                'value': 'true',
                'setting_type': 'boolean',
                'description': 'Validate mass intention amounts (multiples of 500, thanksgiving minimum)'
            },
        ]
        
        for setting in settings_data:
            SystemSetting.objects.get_or_create(
                key=setting['key'],
                defaults=setting
            )
        
        # Initialize group rates
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
        
        self.stdout.write(self.style.SUCCESS('Successfully seeded initial data'))