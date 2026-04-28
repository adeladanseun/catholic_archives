# mass_intentions/serializers.py
from rest_framework import serializers
from .models import MassIntention
from core.models import SystemSetting

class MassIntentionSerializer(serializers.ModelSerializer):
    class Meta:
        model = MassIntention
        fields = '__all__'
        read_only_fields = ['number_of_days', 'is_approved', 'approved_by', 'approved_at']
    
    def validate(self, data):
        validate_amount = True
        try:
            setting = SystemSetting.objects.get(key='validate_intention_amount')
            validate_amount = setting.get_value()
        except SystemSetting.DoesNotExist:
            pass
        
        if validate_amount:
            if data.get('intention_type') == 'thanksgiving':
                if data['amount'] < 3500:
                    raise serializers.ValidationError(
                        "Open thanksgiving requires a minimum of 3,500"
                    )
            elif data.get('intention_type') == 'regular':
                if data['amount'] % 500 != 0:
                    raise serializers.ValidationError(
                        "Regular intentions must be in multiples of 500"
                    )
        
        return data
