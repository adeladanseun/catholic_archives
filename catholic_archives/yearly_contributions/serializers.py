# contributions/serializers.py
from rest_framework import serializers
from .models import YearlyContribution
from core.models import SystemSetting, GroupRate

class ContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = YearlyContribution
        fields = '__all__'
        read_only_fields = ['is_approved', 'approved_by', 'approved_at']
    
    def validate(self, data):
        # Check if validation is enabled
        validate_amount = True
        try:
            setting = SystemSetting.objects.get(key='validate_contribution_amount')
            validate_amount = setting.get_value()
        except SystemSetting.DoesNotExist:
            pass
        
        if validate_amount:
            # Get the current rate for this group at payment date
            rate = GroupRate.objects.filter(
                group_name=data['group_name'],
                effective_from__lte=data['payment_date']
            ).order_by('-effective_from').first()
            
            if rate and data['amount_paid'] != rate.annual_amount:
                raise serializers.ValidationError(
                    f"Expected amount for {data['group_name']} is {rate.annual_amount}. "
                    f"Current rate effective from {rate.effective_from}"
                )
        
        return data

class ContributionListSerializer(serializers.ModelSerializer):
    class Meta:
        model = YearlyContribution
        fields = ['id', 'serial_number', 'payer_name', 'group_name', 'year', 
                 'amount_paid', 'payment_date', 'is_approved']
