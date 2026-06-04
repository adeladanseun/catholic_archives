from django.conf import settings
from rest_framework import serializers
from .models import *
from core.models import SystemSetting
from approvals.serializers import *

class MassIntentionSerializer(serializers.ModelSerializer):
    # Read-only computed fields
    pricing_summary = serializers.SerializerMethodField(read_only=True)
    announcement_schedule = serializers.SerializerMethodField(read_only=True)
    mass_dates_list = serializers.SerializerMethodField(read_only=True)
    type_display = serializers.CharField(source='get_intention_type_display', read_only=True)
    mass_days_display = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = MassIntention
        fields = '__all__'
        read_only_fields = [
            'number_of_days',
            'end_date',
            'is_approved', 
            'approved_by', 
            'approved_at', 
            'recorder',
            'pricing_summary',
            'announcement_schedule',
            'mass_dates_list',
            'type_display',
            'mass_days_display'
        ]
    
    def validate(self, data):
        """Validate amount and dates based on intention type"""
        validate_amount = True
        try:
            setting = SystemSetting.objects.get(key='validate_intention_amount')
            validate_amount = setting.get_value()
        except SystemSetting.DoesNotExist:
            pass
        
        if not validate_amount:
            return data
        
        intention_type = data.get('intention_type')
        amount_paid = data.get('amount_paid')
        thanksgiving_date = data.get('thanksgiving_date')
        mass_date = data.get('mass_date')

        # Validate mass_days if provided
        mass_days = data.get('mass_days', [])
        if mass_days:
            self._validate_mass_days(mass_days)
        
        if not intention_type or not amount_paid:
            raise serializers.ValidationError({
                'critical': 'Intention type or amount paid not set'
            })
        
        regular_price = MassIntention.get_regular_price()
        thanksgiving_price = MassIntention.get_thanksgiving_price()
        combined_price = MassIntention.get_combined_price()
        
        # Validate based on intention type
        if intention_type == MassIntention.REGULAR:
            # if amount_paid % regular_price != 0:
            #     raise serializers.ValidationError({
            #         'amount_paid': f'Regular intentions must be in multiples of {settings.CURRENCY_SYMBOL}{regular_price}'
            #     })
            
            # Ensure thanksgiving_date is not set for regular only
            if thanksgiving_date:
                raise serializers.ValidationError({
                    'thanksgiving_date': 'Thanksgiving date should not be set for regular-only intentions'
                })
        
        elif intention_type == MassIntention.THANKSGIVING:
            if amount_paid < thanksgiving_price:
                raise serializers.ValidationError({
                    'amount_paid': f'Thanksgiving offering minimum is {settings.CURRENCY_SYMBOL}{thanksgiving_price}'
                })
            
            # Thanksgiving must have a date
            if not thanksgiving_date and not data.get('_skip_thanksgiving_date'):
                # If thanksgiving_date not provided, use mass_date
                data['thanksgiving_date'] = mass_date
        
        elif intention_type == MassIntention.BOTH:
            if amount_paid < combined_price:
                raise serializers.ValidationError({
                    'amount_paid': f'Combined intention minimum is {settings.CURRENCY_SYMBOL}{combined_price} ({settings.CURRENCY_SYMBOL}{thanksgiving_price} thanksgiving + {settings.CURRENCY_SYMBOL}{regular_price} per mass day)'
                })
            
            
            # Check that extra amount beyond combined price is in multiples of regular price
            # extra_amount = amount_paid - combined_price
            # if extra_amount > 0 and extra_amount % regular_price != 0:
            #     raise serializers.ValidationError({
            #         'amount_paid': f'Extra days beyond combined must be in multiples of {settings.CURRENCY_SYMBOL}{regular_price}'
            #     })
            
            # Combined must have thanksgiving_date
            if not thanksgiving_date:
                data['thanksgiving_date'] = mass_date
        
        if intention_type == MassIntention.BOTH or intention_type == MassIntention.REGULAR:
            amount_to_pay = len(mass_days)*regular_price #for regular and combined
            if intention_type == MassIntention.BOTH:
                amount_to_pay += thanksgiving_price
            if amount_paid < amount_to_pay:
                raise serializers.ValidationError({
                    'amount_paid': f'You are supposed to pay at least {settings.CURRENCY_SYMBOL}{amount_to_pay}'
                })
        
        
        return data
    
    def validate_intention_type(self, value):
        """Validate intention type choices"""
        valid_types = [MassIntention.REGULAR, MassIntention.THANKSGIVING, MassIntention.BOTH]
        if value not in valid_types:
            raise serializers.ValidationError(
                f'Invalid intention type. Must be one of: {", ".join(valid_types)}'
            )
        return value
    
    def validate_mass_days(self, value):
        """Validate mass_days format"""
        self._validate_mass_days(value)
        return value
    
    def _validate_mass_days(self, mass_days):
        """Helper to validate mass_days list"""
        valid_days = list(range(7))  # 0-6 for Monday-Sunday
        
        if not isinstance(mass_days, list):
            raise serializers.ValidationError({
                'mass_days': 'Must be a list of integers (0=Monday, 6=Sunday)'
            })
        
        for day in mass_days:
            if day not in valid_days:
                raise serializers.ValidationError({
                    'mass_days': f'Invalid day: {day}. Must be 0-6 (0=Monday, 6=Sunday)'
                })
    
    def validate_thanksgiving_date(self, value):
        """Validate thanksgiving date based on intention type"""
        # This runs before the main validate() so we can't check intention_type here
        # The main validate() method handles the cross-field validation
        return value
    
    def get_pricing_summary(self, obj):
        """Get pricing breakdown for display"""
        return obj.get_pricing_summary()
    
    def get_announcement_schedule(self, obj):
        """Get announcement details"""
        return obj.get_announcement_schedule()
    
    def get_mass_dates_list(self, obj):
        """Get list of actual mass dates with day names"""
        if obj.has_regular():
            mass_dates = obj.calculate_mass_dates()
            return [
                {
                    'date': str(date),
                    'day_name': date.strftime('%A'),
                    'day_number': i + 1
                }
                for i, date in enumerate(mass_dates)
            ]
        return []
    
    def get_mass_days_display(self, obj):
        """Get human-readable mass days"""
        day_names = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        if obj.mass_days:
            return [day_names[day] for day in obj.mass_days]
        return [day_names[day] for day in MassIntention.get_default_mass_days()]


class MassIntentionListSerializer(serializers.ModelSerializer):
    # Display fields
    type_display = serializers.CharField(source='get_intention_type_display', read_only=True)
    days = serializers.IntegerField(source='number_of_days', read_only=True)
    has_thanksgiving = serializers.SerializerMethodField(read_only=True)
    has_regular = serializers.SerializerMethodField(read_only=True)
    
    # Summary of dates
    date_summary = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = MassIntention
        fields = [
            'id', 
            'concerned_names', 
            'intention_type',
            'type_display',
            'amount_paid', 
            'mass_date',
            'thanksgiving_date',
            'end_date',
            'intention_text', 
            'number_of_days',
            'days',
            'has_thanksgiving',
            'has_regular',
            'date_summary',
            'mass_days',
            'is_approved', 
            'approved_by', 
            'recorder',
            'created_at'
        ]
    
    def get_has_thanksgiving(self, obj):
        """Check if intention includes thanksgiving component"""
        return obj.has_thanksgiving()
    
    def get_has_regular(self, obj):
        """Check if intention includes regular announcement"""
        return obj.has_regular()
    
    def get_date_summary(self, obj):
        """Get a human-readable summary of the dates"""
        parts = []
        
        if obj.has_regular():
            if obj.number_of_days == 1:
                parts.append(f"Announced on {obj.mass_date}")
            else:
                parts.append(f"Announced from {obj.mass_date}")
                if obj.end_date:
                    parts[-1] += f" to {obj.end_date}"
                parts[-1] += f" ({obj.number_of_days} mass days)"
        
        if obj.has_thanksgiving() and obj.thanksgiving_date:
            if obj.thanksgiving_date == obj.mass_date:
                parts.append("Thanksgiving on same day")
            else:
                parts.append(f"Thanksgiving on {obj.thanksgiving_date}")
        
        return "; ".join(parts) if parts else str(obj.mass_date)


class MassIntentionCalendarSerializer(serializers.ModelSerializer):
    """
    Serializer for calendar view - shows intentions grouped by date.
    Used for building mass schedules and calendars.
    """
    announcement_dates = serializers.SerializerMethodField(read_only=True)
    type_display = serializers.CharField(source='get_intention_type_display', read_only=True)
    
    class Meta:
        model = MassIntention
        fields = [
            'id',
            'concerned_names',
            'intention_text',
            'intention_type',
            'type_display',
            'amount_paid',
            'mass_date',
            'thanksgiving_date',
            'number_of_days',
            'announcement_dates',
            'is_approved'
        ]
    
    def get_announcement_dates(self, obj):
        """Get all dates this intention will be announced"""
        dates = {
            'regular_dates': [],
            'thanksgiving_date': None
        }
        
        if obj.has_regular():
            mass_dates = obj.calculate_mass_dates()
            dates['regular_dates'] = [str(d) for d in mass_dates]
        
        if obj.has_thanksgiving() and obj.thanksgiving_date:
            dates['thanksgiving_date'] = str(obj.thanksgiving_date)
        
        return dates


class MassIntentionBatchReadSerializer(ApprovalBaseBatchReadSerializer):
    class Meta:
        model = MassIntentionApprovalBatch
        item_serializer_class = MassIntentionSerializer
        item_source = 'items'
        fields = ['id', 'items']


class MassIntentionBatchCreateSerializer(ApprovalBaseBatchCreateSerializer):

    class Meta:
        model = MassIntentionApprovalBatch
        fields = ['id', 'item_ids', 'notes', 'money_remitted']
        item_queryset = MassIntention.objects.all()
        item_source = 'items'

    def check_item_requirements(self, item):
        if item.batch is not None:
            raise serializers.ValidationError(f"Item {item.id} already in a batch.")
        if item.is_approved:
            raise serializers.ValidationError(f"Item {item.id} is already approved.")