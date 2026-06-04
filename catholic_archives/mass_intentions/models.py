from datetime import timedelta, date
import json

from django.core.exceptions import ValidationError
from django.db import models
from django.core.validators import MinValueValidator
from django.conf import settings

from approvals.models import ApprovalItem, ApprovalBatch
from core.models import SystemSetting, DateModel


class MassIntentionApprovalBatch(ApprovalBatch):
    pass


class MassIntention(ApprovalItem):
    REGULAR = 'regular'
    THANKSGIVING = 'thanksgiving'
    BOTH = 'both'
    
    INTENTION_TYPE = [
        (REGULAR, 'Regular Intention'),
        (THANKSGIVING, 'Open Thanksgiving'),
        (BOTH, 'Regular + Thanksgiving'),
    ]
    
    # Pricing constants
    REGULAR_PRICE = 500
    THANKSGIVING_PRICE = 3000
    COMBINED_PRICE = 3500  # REGULAR_PRICE + THANKSGIVING_PRICE
    
    batch = models.ForeignKey(
        MassIntentionApprovalBatch, 
        on_delete=models.SET_NULL, 
        related_name='items', 
        null=True,
        blank=True
    )
    
    # The date the first announcement starts
    mass_date = models.DateField(
        help_text="Start date for the mass intention announcements"
    )
    
    # Thanksgiving date (can be different from mass start date)
    thanksgiving_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date for thanksgiving mass (usually Sunday). Required for thanksgiving/both types."
    )
    
    # End date for regular intentions (calculated or manually set)
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End date for regular intention announcements. Auto-calculated if not set."
    )
    
    # Mass days schedule (which days of the week masses are held)
    mass_days = models.JSONField(
        default=list,
        blank=True,
        help_text="List of days when masses are held, e.g., [0, 6] for Sundays and Saturdays (0=Monday, 6=Sunday)"
    )
    
    concerned_names = models.CharField(
        max_length=500, 
        help_text="Can be individual, group, or anonymous (e.g., 'The Choir', 'Mr and Mrs Obi')"
    )
    intention_text = models.TextField()
    intention_type = models.CharField(max_length=20, choices=INTENTION_TYPE)
    amount_paid = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(500)]
    )
    number_of_days = models.IntegerField(
        default=1, 
        help_text="Number of mass days the intention will be announced"
    )
    
    class Meta:
        db_table = 'mass_intentions'
        ordering = ['mass_date', '-created_at']
        indexes = [
            models.Index(fields=['mass_date']),
            models.Index(fields=['intention_type']),
            models.Index(fields=['thanksgiving_date']),
        ]
    
    def __str__(self):
        type_display = dict(self.INTENTION_TYPE).get(self.intention_type, '')
        dates = f"{self.mass_date}"
        if self.thanksgiving_date and self.thanksgiving_date != self.mass_date:
            dates += f" (Thanksgiving: {self.thanksgiving_date})"
        return f"{dates} - {self.concerned_names}: [{type_display}] {self.intention_text[:50]}"
    
    @classmethod
    def get_regular_price(cls):
        """Get regular intention price from settings or default"""
        try:
            setting = SystemSetting.objects.get(key='regular_intention_price')
            if setting.get_value():
                return int(setting.value)
        except SystemSetting.DoesNotExist:
            pass
        return cls.REGULAR_PRICE
    
    @classmethod
    def get_thanksgiving_price(cls):
        """Get thanksgiving price from settings or default"""
        try:
            setting = SystemSetting.objects.get(key='thanksgiving_intention_price')
            if setting.get_value():
                return int(setting.value)
        except SystemSetting.DoesNotExist:
            pass
        return cls.THANKSGIVING_PRICE
    
    @classmethod
    def get_combined_price(cls):
        """Get combined price (regular + thanksgiving)"""
        return cls.get_regular_price() + cls.get_thanksgiving_price()
    
    @classmethod
    def get_default_mass_days(cls):
        """Get default mass days from settings or use Sunday only"""
        try:
            setting = SystemSetting.objects.get(key='default_mass_days')
            if setting.get_value():
                return json.loads(setting.value)
        except (SystemSetting.DoesNotExist, json.JSONDecodeError):
            pass
        return [6]  # Default: Sunday only (6 = Sunday)
    
    def clean(self):
        """Validate the intention"""
        
        thanksgiving_price = self.get_thanksgiving_price()
        regular_price = self.get_regular_price()
        
        # Type-specific validations
        if self.intention_type in [self.THANKSGIVING, self.BOTH]:
            if not self.thanksgiving_date:
                raise ValidationError({
                    'thanksgiving_date': 'Thanksgiving date is required for thanksgiving and combined intentions'
                })
        
        if self.thanksgiving_date and self.intention_type == self.REGULAR:
            raise ValidationError({
                'thanksgiving_date': 'Thanksgiving date should not be set for regular-only intentions'
            })
        
        # Amount validation
        if self.intention_type == self.REGULAR:
            if self.amount_paid < (regular_price * self.number_of_days):
                raise ValidationError({
                    'amount_paid': f'For {self.number_of_days} day(s), amount must be at least {regular_price * self.number_of_days}'
                })
        
        elif self.intention_type == self.THANKSGIVING:
            if self.amount_paid < thanksgiving_price:
                raise ValidationError({
                    'amount_paid': f'Thanksgiving minimum is {settings.CURRENCY_SYMBOL}{thanksgiving_price}'
                })
        
        elif self.intention_type == self.BOTH:
            combined_price = self.get_combined_price()
            if self.amount_paid < combined_price:
                raise ValidationError({
                    'amount_paid': f'Combined intention minimum is {settings.CURRENCY_SYMBOL}{combined_price}'
                })
            
            remaining = self.amount_paid - thanksgiving_price
            if remaining >= regular_price and remaining < (regular_price * self.number_of_days):
                raise ValidationError({
                    'amount_paid': f'Amount for extra days must exceed {settings.CURRENCY_SYMBOL}{regular_price * self.number_of_days}'
                })
    
    def calculate_mass_dates(self):
        """
        Calculate the actual dates when the intention will be announced.
        Returns list of dates based on mass_days schedule.
        """
        if not self.mass_days:
            self.mass_days = self.get_default_mass_days()
        
        mass_dates = []
        current_date = self.mass_date
        days_counted = 0
        
        # Look ahead up to 90 days to find enough mass days
        max_days_ahead = 90
        
        for i in range(max_days_ahead):
            check_date = current_date + timedelta(days=i)
            # Check if this day is a mass day (0=Monday, 6=Sunday)
            if check_date.weekday() in self.mass_days:
                mass_dates.append(check_date)
                days_counted += 1
                if days_counted >= self.number_of_days:
                    break
        
        return mass_dates
    
    @property
    def days_left(self):
        """How many more times this intention needs to be read"""
        if not self.has_regular():
            return 0
        
        scheduled = self.calculate_mass_dates()
        today = date.today()
        read_dates = set(
            self.readings.filter(was_read=True).values_list('scheduled_date', flat=True)
        )
        remaining = [d for d in scheduled if d not in read_dates and d >= today]
        return len(remaining)
    
    @property
    def readings_completed(self):
        """Summary of completed vs scheduled readings"""
        if not self.has_regular():
            return None
        
        scheduled = self.calculate_mass_dates()
        read_count = self.readings.filter(was_read=True).count()
        return {
            'completed': read_count,
            'total': len(scheduled),
            'remaining': len(scheduled) - read_count,
            'display': f"{read_count}/{len(scheduled)}"
        }
    
    def save(self, *args, **kwargs):
        # Set default mass days if not specified
        if not self.mass_days:
            self.mass_days = self.get_default_mass_days()
        
        # Auto-calculate number_of_days
        regular_price = self.get_regular_price()
        
        if self.intention_type == self.REGULAR:
            self.thanksgiving_date = None  # No thanksgiving for regular only
        
        elif self.intention_type == self.THANKSGIVING:
            self.number_of_days = 1  # One mass for thanksgiving
            if not self.thanksgiving_date:
                self.thanksgiving_date = self.mass_date  # Default to same date
        
        elif self.intention_type == self.BOTH:
            if not self.thanksgiving_date:
                self.thanksgiving_date = self.mass_date
        
        # Calculate end_date if not set
        if not self.end_date and self.number_of_days > 1:
            mass_dates = self.calculate_mass_dates()
            if mass_dates:
                self.end_date = mass_dates[-1]
        
        # Run validation
        if not kwargs.pop('skip_validation', False):
            self.clean()
        
        super().save(*args, **kwargs)
    
    def has_regular(self):
        """Check if this intention includes regular announcement"""
        return self.intention_type in [self.REGULAR, self.BOTH]
    
    def has_thanksgiving(self):
        """Check if this intention includes thanksgiving"""
        return self.intention_type in [self.THANKSGIVING, self.BOTH]
    
    def get_announcement_schedule(self):
        """Get the detailed announcement schedule"""
        regular_price = self.get_regular_price()
        thanksgiving_price = self.get_thanksgiving_price()
        mass_dates = self.calculate_mass_dates() if self.has_regular() else []
        
        schedule = {
            'intention_type': self.get_intention_type_display(),
            'mass_dates': mass_dates,
            'thanksgiving_date': str(self.thanksgiving_date) if self.thanksgiving_date else None,
        }
        
        if self.intention_type == self.REGULAR:
            schedule.update({
                'announcements': f'Announced on {len(mass_dates)} mass day(s)',
                'dates': [str(d) for d in mass_dates],
                'breakdown': f'{self.number_of_days} day(s) × {settings.CURRENCY_SYMBOL}{regular_price}'
            })
        elif self.intention_type == self.THANKSGIVING:
            schedule.update({
                'announcements': f'Thanksgiving on {self.thanksgiving_date}',
                'breakdown': f'Thanksgiving: {settings.CURRENCY_SYMBOL}{self.amount_paid}'
            })
        elif self.intention_type == self.BOTH:
            schedule.update({
                'announcements': f'Thanksgiving on {self.thanksgiving_date} + Regular on {len(mass_dates)} mass day(s)',
                'thanksgiving': f'{settings.CURRENCY_SYMBOL}{thanksgiving_price} on {self.thanksgiving_date}',
                'regular_dates': [str(d) for d in mass_dates],
                'breakdown': f'Thanksgiving: {settings.CURRENCY_SYMBOL}{thanksgiving_price} + {self.number_of_days} day(s) × {settings.CURRENCY_SYMBOL}{regular_price}'
            })
        
        return schedule
    
    def get_pricing_summary(self):
        """Get pricing breakdown for display"""
        regular_price = self.get_regular_price()
        thanksgiving_price = self.get_thanksgiving_price()
        
        summary = {
            'total': f'{settings.CURRENCY_SYMBOL}{self.amount_paid}',
            'type': self.get_intention_type_display(),
        }
        
        if self.intention_type == self.REGULAR:
            summary.update({
                'rate': f'{settings.CURRENCY_SYMBOL}{regular_price} per mass day',
                'days': self.number_of_days,
                'calculation': f'{self.number_of_days} day(s) × {settings.CURRENCY_SYMBOL}{regular_price}',
                'paid_more': True if self.number_of_days * regular_price < self.amount_paid else False
            })
        elif self.intention_type == self.THANKSGIVING:
            summary.update({
                'minimum': f'{settings.CURRENCY_SYMBOL}{thanksgiving_price}',
                'thanksgiving_date': str(self.thanksgiving_date),
                'paid_more': True if thanksgiving_price < self.amount_paid else False
            })
        elif self.intention_type == self.BOTH:
            regular_portion = self.amount_paid - thanksgiving_price
            summary.update({
                'thanksgiving': f'{settings.CURRENCY_SYMBOL}{thanksgiving_price} on {self.thanksgiving_date}',
                'regular_rate': f'{settings.CURRENCY_SYMBOL}{regular_price} per mass day',
                'regular_days': self.number_of_days,
                'calculation': f'Thanksgiving ({settings.CURRENCY_SYMBOL}{thanksgiving_price}) + {self.number_of_days} day(s) × {settings.CURRENCY_SYMBOL}{regular_price}',
                'paid_more': True if ((self.number_of_days * regular_price) + thanksgiving_price) < self.amount_paid else False
            })
        
        return summary


class MassIntentionReading(DateModel):
    """
    Tracks whether a scheduled mass intention was actually read on a given date.
    Handles cases where mass is canceled or intention is skipped.
    """
    mass_intention = models.ForeignKey(
        MassIntention,
        on_delete=models.CASCADE,
        related_name='readings'
    )
    scheduled_date = models.DateField()
    was_read = models.BooleanField(default=True)
    skipped_reason = models.TextField(
        blank=True,
        help_text="e.g., 'Mass canceled due to holiday', 'Priest unavailable', 'Time constraints'"
    )
    read_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who confirmed this reading (usually secretary or priest)"
    )
    
    class Meta:
        db_table = 'mass_intention_readings'
        unique_together = ['mass_intention', 'scheduled_date']
        ordering = ['scheduled_date']
    
    def __str__(self):
        status = "✓ Read" if self.was_read else "✗ Skipped"
        return f"{self.scheduled_date} - {self.mass_intention.concerned_names} - {status}"