from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import exceptions
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from core.permissions import IsPriestUser, IsSecretary, IsAuthenticated


class BaseApprovalBatchViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for approval batch workflows.
    
    Features:
    - POST: Create batch with items by ID
    - GET: List & Retrieve with detailed item information
    - PUT/PATCH: Update batch metadata (only if not approved)
    - DELETE: Destroy batch (unlinks items, only if not approved)
    - Custom actions: approve, reject, pending
    
    Permission Matrix:
    - create: Secretary only
    - update/partial_update: Priest only (only on unapproved batches)
    - destroy: Priest only (only on unapproved batches)
    - list/retrieve: Any authenticated user
    """
    
    read_serializer_class = None
    create_serializer_class = None
    update_serializer_class = None
    
    def get_serializer_class(self):
        """Dynamically select serializer based on action"""
        if self.action in ['create', 'create_batch']:
            return self.create_serializer_class or self.read_serializer_class
        
        if self.action in ['update', 'partial_update']:
            return self.update_serializer_class or self.read_serializer_class
        
        return self.read_serializer_class
    
    def get_permissions(self):
        """Permission matrix for batch operations"""
        permission_map = {
            'create': [IsSecretary],
            'create_batch': [IsSecretary],
            'update': [IsPriestUser],
            'partial_update': [IsPriestUser],
            'destroy': [IsPriestUser],
            'approve': [IsPriestUser],
            'reject': [IsPriestUser],
            'list': [IsAuthenticated],
            'retrieve': [IsAuthenticated],
            'pending': [IsAuthenticated],
            'summary': [IsAuthenticated],
        }
        
        permissions = permission_map.get(self.action, [IsPriestUser])
        self.permission_classes = permissions
        return [permission() for permission in permissions]
    
    def get_queryset(self):
        """Default queryset from the read serializer's model"""
        if self.read_serializer_class:
            return self.read_serializer_class.Meta.model.objects.all()
        return super().get_queryset()
    
    @swagger_auto_schema(
        operation_description="Create a new approval batch with items",
        responses={
            201: "Batch created successfully",
            400: "Validation Error",
            403: "Permission Denied"
        }
    )
    def create(self, request, *args, **kwargs):
        """Create a batch with items by their IDs. Requires secretary permissions."""
        try:
            return super().create(request, *args, **kwargs)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @swagger_auto_schema(
        operation_description="Update batch metadata (only if not approved)",
        responses={
            200: "Batch updated successfully",
            400: "Validation Error",
            403: "Permission Denied"
        }
    )
    def update(self, request, *args, **kwargs):
        """Update batch metadata. Cannot update approved batches."""
        return super().update(request, *args, **kwargs)
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update for batch. Cannot update approved batches."""
        return super().partial_update(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Set the raised_by field and save"""
        serializer.save(raised_by=self.request.user)
    
    def perform_update(self, serializer):
        """Prevent updates on approved batches"""
        instance = serializer.instance
        if instance.is_approved:
            raise exceptions.PermissionDenied(
                "Cannot update an approved batch."
            )
        serializer.save()
    
    def perform_destroy(self, instance):
        """Prevent deletion of approved batches"""
        if instance.is_approved:
            raise exceptions.PermissionDenied(
                "Cannot delete an approved batch. "
                "Only pending or rejected batches can be deleted."
            )
        self.unlink_items_from_batch(instance)
        instance.delete()
    
    def unlink_items_from_batch(self, instance):
        """Unlink all items from this batch. Override for custom handling."""
        if hasattr(instance, 'items'):
            instance.items.update(
                batch=None,
                is_approved=False,
                approved_by=None,
                approved_at=None
            )
    
    @swagger_auto_schema(
        operation_description="Get all pending items not yet in a batch",
        responses={200: "List of pending items"}
    )
    @action(detail=False, methods=['get'], url_path='pending')
    def pending(self, request):
        """View all items that haven't been batched yet."""
        if not self.read_serializer_class:
            return Response(
                {'error': 'Read serializer not configured'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        item_serializer = getattr(
            self.read_serializer_class.Meta, 
            'item_serializer_class', 
            None
        )
        
        if not item_serializer:
            return Response(
                {'error': 'Item serializer not configured'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        item_model = item_serializer.Meta.model
        unbatched_items = item_model.objects.filter(batch__isnull=True)
        
        serializer = item_serializer(unbatched_items, many=True, context={'request': request})
        return Response({
            'count': unbatched_items.count(),
            'items': serializer.data
        })
    
    @swagger_auto_schema(
        operation_description="Get batch summary with totals",
        responses={200: "Batch summary"}
    )
    @action(detail=True, methods=['get'], url_path='summary')
    def summary(self, request, pk=None):
        """Get detailed summary of a batch including totals."""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        
        total_amount = 0
        item_count = 0
        
        if hasattr(instance, 'items'):
            items = instance.items.all()
            item_count = items.count()
            total_amount = sum(
                item.amount_paid if hasattr(item, 'amount_paid') else 0 
                for item in items
            )
        
        return Response({
            'batch': serializer.data,
            'summary': {
                'total_items': item_count,
                'total_amount': total_amount,
            }
        })
    
    @swagger_auto_schema(
        operation_description="Approve all items in a batch (Priest only)",
        responses={
            200: "Batch approved successfully",
            400: "Validation Error",
            403: "Permission Denied"
        }
    )
    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        """Priest approves all items in the batch."""
        instance = self.get_object()
        
        if not request.user.is_priest and not request.user.is_staff:
            return Response(
                {'error': 'Only priests can approve batches'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            with transaction.atomic():
                instance.approve_batch(approved_by=request.user)
                
                return Response({
                    'message': 'Batch approved successfully',
                    'approved_items': instance.items.count(),
                    'batch_id': instance.id
                })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @swagger_auto_schema(
        operation_description="Reject batch and unlink all items (Priest only)",
        responses={
            200: "Batch rejected successfully",
            400: "Validation Error",
            403: "Permission Denied"
        }
    )
    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        """Priest rejects batch and returns items to pending state."""
        instance = self.get_object()
        
        if not request.user.is_priest and not request.user.is_staff:
            return Response(
                {'error': 'Only priests can reject batches'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        reason = request.data.get('reason', '')
        
        try:
            with transaction.atomic():
                instance.reject_batch(rejected_by=request.user, reason=reason)
                
                return Response({
                    'message': 'Batch rejected and items returned to pending',
                    'batch_id': instance.id,
                    'reason': reason
                })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )