# approvals/serializers.py
from rest_framework import serializers
from .models import ApprovalBatch, ApprovalItem
from yearly_contributions.models import YearlyContribution
from mass_intentions.models import MassIntention
from django.contrib.contenttypes.models import ContentType

class ApprovalItemSerializer(serializers.ModelSerializer):
    record_type = serializers.SerializerMethodField()
    record_details = serializers.SerializerMethodField()
    
    class Meta:
        model = ApprovalItem
        fields = ['id', 'content_type', 'object_id', 'record_type', 'record_details']
    
    def get_record_type(self, obj):
        return obj.content_type.model
    
    def get_record_details(self, obj):
        if obj.content_object:
            return {
                'id': obj.content_object.id,
                'amount': str(obj.content_object.amount_paid if hasattr(obj.content_object, 'amount_paid') else obj.content_object.amount),
                'date': str(obj.content_object.payment_date if hasattr(obj.content_object, 'payment_date') else obj.content_object.mass_date),
                'description': str(obj.content_object)
            }
        return None

class ApprovalBatchSerializer(serializers.ModelSerializer):
    items = ApprovalItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = ApprovalBatch
        fields = '__all__'
        read_only_fields = ['total_amount', 'record_count']

class BatchApprovalSerializer(serializers.Serializer):
    """Serializer for creating a batch approval"""
    batch_type = serializers.ChoiceField(choices=ApprovalBatch.BATCH_TYPES)
    priest_name = serializers.CharField(max_length=100)
    notes = serializers.CharField(required=False, allow_blank=True)
    contribution_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        required=False
    )
    mass_intention_ids = serializers.ListField(
        child=serializers.IntegerField(), 
        required=False
    )
    
    def validate(self, data):
        if not data.get('contribution_ids') and not data.get('mass_intention_ids'):
            raise serializers.ValidationError(
                "Must provide at least one YearlyContribution or mass intention ID"
            )
        return data
