# approvals/serializers.py
from rest_framework import serializers
from .models import ApprovalBatch, ApprovalItem
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

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

class BaseBatchCreateSerializer(serializers.ModelSerializer):
    # Define the field generically
    item_ids = serializers.PrimaryKeyRelatedField(many=True, queryset=None)

    def __init__(self, *args, **kwargs):
        # 1. Pull custom config passed from the subclass or Meta
        self.item_queryset = getattr(self.Meta, 'item_queryset', None)
        self.item_source = getattr(self.Meta, 'item_source', 'items')

        super().__init__(*args, **kwargs)

        # 2. Apply the variable config to the field
        if 'item_ids' in self.fields:
            self.fields['item_ids'].queryset = self.item_queryset
            self.fields['item_ids'].source = self.item_source

    # ... keep your validate and create methods here ...
    def validate_item_ids(self, items):
        """Template for validation - override 'check_item' in child classes"""
        for item in items:
            self.check_item_requirements(item)
        return items

    def check_item_requirements(self, item):
        """Override this in the child class for specific logic"""
        raise NotImplementedError("Subclasses must implement check_item_requirements")

    @transaction.atomic
    def create(self, validated_data):
        user = self.context['request'].user
        items = validated_data.pop(self.item_source, [])
        
        # 1. Create the Batch
        batch = self.Meta.model.objects.create(**validated_data, raised_by=user)
        
        # 2. Link the items
        self.link_items_to_batch(batch, items, user)
            
        return batch

    def link_items_to_batch(self, batch, items, user):
        """Default linking logic for Reverse FK"""
        for item in items:
            item.batch = batch
            item.recorder = user
            item.save()