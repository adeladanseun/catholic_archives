from decimal import Decimal

from django.db.models import Sum
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import ApprovalBatch, ApprovalItem
from .serializers import (
    ApprovalBatchSerializer, 
    BatchApprovalSerializer,
    ApprovalItemSerializer
)
from core.permissions import *
from yearly_contributions.models import YearlyContribution
from mass_intentions.models import MassIntention

# class ApprovalBatchViewSet(viewsets.ModelViewSet):
#     """
#     Priest approval workflow for contributions and mass intentions.
    
#     ## Only Priests Can:
#     - Create approval batches
#     - View pending approvals
#     - Approve/reject records
    
#     ## Features
#     - Batch approve multiple records at once
#     - Track who approved what and when
#     - View pending approvals with totals
#     """
#     #queryset = ApprovalBatch.objects.all()
#     serializer_class = ApprovalBatchSerializer
#     permission_classes = [IsPriestUser]
    
#     def get_permissions(self):
#         """
#         Only priests can create approvals, but everyone can view
#         """
#         #if self.action in ['create', 'create_batch', 'update', 'partial_update', 'destroy']:
#         if self.action in ['create', 'create_batch', 'destroy']:
#             self.permission_classes = [IsSecretary]

#         elif self.action in ['update', 'partial_update', 'destroy']:
#             self.permission_classes = [IsPriestUser]

#         elif self.action == 'list':
#             self.permission_classes = [IsAuthenticated]  # Everyone can view
        
#         else:
#             self.permission_classes = [IsPriestUser]
        
#         return super().get_permissions()
    
#     def get_serializer_class(self):
#         if self.action == 'create_batch':
#             return BatchApprovalSerializer
#         return ApprovalBatchSerializer
    
#     @swagger_auto_schema(
#         operation_description="Create a batch approval for multiple records",
#         request_body=BatchApprovalSerializer,
#         responses={
#             201: ApprovalBatchSerializer,
#             400: "Validation Error",
#             403: "Permission Denied - Priest only"
#         }
#     )
#     @action(detail=False, methods=['post'])
#     def create_batch(self, request):
#         """Secretary creates an approval batch"""
#         serializer = BatchApprovalSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
        
#         data = serializer.validated_data
        
#         with transaction.atomic():
#             batch = ApprovalBatch.objects.create(
#                 batch_type=data['batch_type'],
#                 raised_by=request.user,
#                 notes=data.get('notes', '')
#             )
            
#             total_amount = Decimal('0.00')
            
#             # Process contributions
#             if data.get('contribution_ids'):
#                 contribution_ct = ContentType.objects.get_for_model(YearlyContribution)
#                 contributions = YearlyContribution.objects.filter(
#                     id__in=data['contribution_ids'],
#                     is_approved=False
#                 )
                
#                 for contribution in contributions:
#                     ApprovalItem.objects.create(
#                         batch=batch,
#                         content_type=contribution_ct,
#                         object_id=contribution.id
#                     )
#                     contribution.is_approved = True
#                     contribution.approved_by = request.user.get_full_name()
#                     contribution.save()
#                     total_amount += contribution.amount_paid
            
#             # Process mass intentions
#             if data.get('mass_intention_ids'):
#                 intention_ct = ContentType.objects.get_for_model(MassIntention)
#                 intentions = MassIntention.objects.filter(
#                     id__in=data['mass_intention_ids'],
#                     is_approved=False
#                 )
                
#                 for intention in intentions:
#                     ApprovalItem.objects.create(
#                         batch=batch,
#                         content_type=intention_ct,
#                         object_id=intention.id
#                     )
#                     intention.is_approved = True
#                     intention.approved_by = request.user.get_full_name()
#                     intention.save()
#                     total_amount += intention.amount
            
#             batch.total_amount = total_amount
#             batch.record_count = batch.items.count()
#             batch.save()
        
#         return Response(
#             ApprovalBatchSerializer(batch).data,
#             status=status.HTTP_201_CREATED
#         )
    
#     @swagger_auto_schema(
#         operation_description="Get all unapproved records pending priest review",
#         responses={
#             200: openapi.Response(
#                 description="Pending records for review",
#                 examples={
#                     "application/json": {
#                         "contributions": {
#                             "records": [],
#                             "count": 5,
#                             "total_amount": "5000"
#                         },
#                         "mass_intentions": {
#                             "records": [],
#                             "count": 3,
#                             "total_amount": "1500"
#                         },
#                         "grand_total": "6500"
#                     }
#                 }
#             )
#         }
#     )
#     @action(detail=False, methods=['get'])
#     def pending_approvals(self, request):
#         """Get all unapproved records for priest review"""
#         unapproved_contributions = YearlyContribution.objects.filter(
#             is_approved=False
#         ).values('id', 'payer_name', 'amount_paid', 'payment_date', 'group_name', 'year')
        
#         unapproved_intentions = MassIntention.objects.filter(
#             is_approved=False
#         ).values('id', 'concerned_names', 'amount', 'mass_date', 'intention_type')
        
#         total_contribution_amount = YearlyContribution.objects.filter(
#             is_approved=False
#         ).aggregate(total=Sum('amount_paid'))['total'] or 0
        
#         total_intention_amount = MassIntention.objects.filter(
#             is_approved=False
#         ).aggregate(total=Sum('amount'))['total'] or 0
        
#         return Response({
#             'contributions': {
#                 'records': unapproved_contributions,
#                 'count': len(unapproved_contributions),
#                 'total_amount': total_contribution_amount
#             },
#             'mass_intentions': {
#                 'records': unapproved_intentions,
#                 'count': len(unapproved_intentions),
#                 'total_amount': total_intention_amount
#             },
#             'grand_total': total_contribution_amount + total_intention_amount
#         })