# core/management/commands/create_job_data.py
from django.core.management.base import BaseCommand
from mass_intentions.models import MassIntention
from yearly_contributions.models import YearlyContribution
from django.contrib.auth import get_user_model
from datetime import date
from random import randint, choice

class Command(BaseCommand):
    help = 'Seed initial data for church management system'
    
    def handle(self, *args, **kwargs):
        #Generate Mass Intention Data
        recorder = get_user_model().objects.get(username='secretary')
        if not recorder:
            recorder = get_user_model().objects.create(
                username='secretary',
                email='seun@church.com',
                role='secretary',
            )
        recorder.set_password('secretary')

        if not MassIntention.objects.count():
            self.stdout.write(self.style.NOTICE("Creating mass intention data..."))
            for i in range(1, 101):
                intention_type='regular' if i % 2 == 0 else 'thanksgiving'
                MassIntention.objects.create(
                    mass_date=date(1950+i, i % 12 + 1, i % 30 + 1),
                    concerned_names=choice([f"Person {i}", "choir", "The CMO", 'The CWO', 'Sacred Heart', 'St Jude', 'Legion of Mary', 'Charismatic']),
                    intention_text=f"Intention text for Person {i}",
                    intention_type=intention_type,
                    amount=(500 * (i % 5 + 1)) if intention_type=='regular' else 3200,
                    recorder=recorder
                )
            self.stdout.write(self.style.SUCCESS("Created mass intention data..."))
        else:
            self.stdout.write(self.style.ERROR("Mass intentions already exist. Skipping mass intention data creation."))

        if not YearlyContribution.objects.count():
            self.stdout.write(self.style.NOTICE("Creating yearly contribution data..."))
            
            group_name = {'men':1000, 'women':500, 'youth':300, 'children':100}
            for i in range(1, 101):
                chosen_name = choice(list(group_name.keys()))
                YearlyContribution.objects.create(
                    payer_name=f"Payer {abs(i-randint(1,50))}",
                    amount_paid=group_name[chosen_name],
                    payment_date=date(1950+i, 1, i % 30 + 1),
                    year=1950+i,
                    group_name=(chosen_name),
                    recorder=recorder
                )
            self.stdout.write(self.style.SUCCESS("Created yearly contribution data..."))
        else:
            self.stdout.write(self.style.ERROR("Yearly contributions already exist. Skipping yearly contribution data creation."))