from rest_framework import serializers
from .models import YearlyContribution, YearlyContributionApprovalBatch
from core.models import SystemSetting, GroupRate
from approvals.serializers import *

class ContributionSerializer(serializers.ModelSerializer):
    class Meta:
        model = YearlyContribution
        fields = '__all__'
        read_only_fields = ['is_approved', 'approved_by', 'approved_at', 'recorder']
    
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
        fields = ['id', 'payer_name', 'group_name', 'year', 
                 'amount_paid', 'payment_date', 'is_approved', 'approved_by', 'recorder']

class ContributionBatchReadSerializer(ApprovalBaseBatchReadSerializer):
    class Meta:
        model = YearlyContributionApprovalBatch
        # The specific serializer for the items
        item_serializer_class = ContributionSerializer 
        # The related_name on the ForeignKey
        item_source = 'items' 
        fields = ['id', 'notes', 'created_at']


class ContributionBatchCreateSerializer(ApprovalBaseBatchCreateSerializer):

    class Meta:
        model = YearlyContributionApprovalBatch
        fields = ['id', 'item_ids', 'notes', 'money_remitted']
        item_queryset = YearlyContribution.objects.all()
        item_source = 'items'

    def check_item_requirements(self, item):
        if item.batch is not None:
            raise serializers.ValidationError(f"Item {item.id} already in a batch.")
        if item.is_approved:
            raise serializers.ValidationError(f"Item {item.id} is already approved.")


# class ContributionBatchCreateSerializer(serializers.ModelSerializer):
#     # This specifically accepts a list of IDs from the frontend
#     contribution_ids = serializers.PrimaryKeyRelatedField(
#         many=True,
#         queryset=YearlyContribution.objects.all(),
#         source='items'  # Maps 'contribution_ids' to the 'contributions' field on your model
#     )

#     class Meta:
#         model = YearlyContributionApprovalBatch
#         fields = ['id', 'contribution_ids', 'notes', 'money_remitted'] # Add your other batch fields here
    
#     def validate_contribution_ids(self, value):
#         """
#         'value' is a list of YearlyContribution instances 
#         (DRF has already converted the IDs to objects).
#         """
#         for contribution in value:
#             #Check if already in another batch
#             if contribution.batch is not None:
#                 raise serializers.ValidationError(
#                     f"Contribution {contribution.id} is already assigned to a batch."
#                 )

#             if contribution.is_approved:
#                 raise serializers.ValidationError(
#                     f"Contribution {contribution.id} is already approved and cannot be batched."
#                 )
            
#             #other custom requirements here...
        
#         return value

#     def create(self, validated_data):
#         user = self.context['request'].user
#         # The 'contributions' list here is now guaranteed to be valid
#         contributions = validated_data.pop('contributions', [])
#         batch = YearlyContributionApprovalBatch.objects.create(**validated_data, raised_by=user)
        
#         # Efficiently update the FK on all contributions at once
#         for contribution in contributions:
#             contribution.batch = batch
#             contribution.recorder = user
#             contribution.save()
            
#         return batch
