# approvals/serializers.py
from rest_framework import serializers
from .models import ApprovalBatch, ApprovalItem
from django.db import transaction

class ApprovalBaseBatchReadSerializer(serializers.ModelSerializer):
    # This acts as a placeholder; we inject the real serializer in __init__
    items = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        # Pull the specific child serializer from Meta
        self.item_serializer_class = getattr(self.Meta, 'item_serializer_class', None)
        self.item_source = getattr(self.Meta, 'item_source', 'items')
        
        if self.item_serializer_class is None:
            raise AssertionError(
                f"{self.__class__.__name__} must define 'item_serializer_class' in Meta."
            )
            
        return super().__init__(*args, **kwargs)

    def get_items(self, obj):
        # Fetch the related objects using the dynamic source name
        queryset = getattr(obj, self.item_source).all()
        # Use the injected serializer to represent them
        return self.item_serializer_class(queryset, many=True, context=self.context).data


class ApprovalBaseBatchCreateSerializer(serializers.ModelSerializer):
    # Define the field generically
    item_ids = serializers.PrimaryKeyRelatedField(many=True, queryset=ApprovalItem)

    def __init__(self, *args, **kwargs):
        # 1. Pull custom config passed from the subclass or Meta
        self.item_queryset = getattr(self.Meta, 'item_queryset', None)
        self.item_source = getattr(self.Meta, 'item_source', 'items')

        if self.item_queryset is None:
            raise AssertionError(
                f"{self.__class__.__name__} must define 'item_queryset' in Meta."
            )

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