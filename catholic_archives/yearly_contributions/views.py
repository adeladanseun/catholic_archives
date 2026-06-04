from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response

from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import YearlyContribution, YearlyContributionApprovalBatch
from .serializers import (
    ContributionSerializer,
    ContributionListSerializer,
    ContributionBatchReadSerializer,
    ContributionBatchCreateSerializer,
)
from core.permissions import *
from core.views import GenericModelViewSet
from approvals.views import BaseApprovalBatchViewSet


class ContributionViewSet(GenericModelViewSet):
    """
    ViewSet for managing yearly contributions.
    
    Permissions:
    - Secretary: Create, view, update contributions
    - Priest/Admin: Full access including approval
    
    Features:
    - Filter by year, group, payment status
    - Search by payer name
    - Summary reports by year/group
    - Track recording user automatically
    """
    queryset = YearlyContribution.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['year', 'group_name', 'is_approved', 'payment_date', 'batch']
    search_fields = ['payer_name']
    ordering_fields = ['payment_date', 'amount_paid', 'year', 'created_at']
    ordering = ['-payment_date', '-created_at']

    list_serializer = ContributionListSerializer
    regular_serializer = ContributionSerializer
    
    def perform_create(self, serializer):
        """Automatically set the recorder to the current user"""
        serializer.save(recorder=self.request.user)
    
    def perform_update(self, serializer):
        """Track who last modified the record"""
        super().perform_update(serializer)
    
    @swagger_auto_schema(
        operation_description="Get contribution summary grouped by year and category",
        manual_parameters=[
            openapi.Parameter('year', openapi.IN_QUERY, description="Filter by specific year", type=openapi.TYPE_INTEGER),
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Filter from date (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="Filter to date (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
        ],
        responses={
            200: openapi.Response(
                description="Contribution summary",
                examples={
                    "application/json": {
                        "by_group": [
                            {
                                "group_name": "men",
                                "total_amount": "50000",
                                "count": 50,
                                "approved_amount": "45000",
                                "unapproved_amount": "5000"
                            }
                        ],
                        "by_year": [
                            {
                                "year": 2024,
                                "total_amount": "150000",
                                "count": 150
                            }
                        ],
                        "overall": {
                            "total_amount": "150000",
                            "total_count": 150,
                            "approved_count": 130,
                            "unapproved_count": 20
                        }
                    }
                }
            )
        }
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get comprehensive contribution summaries"""
        queryset = self.get_queryset()
        
        year = request.query_params.get('year')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if year:
            queryset = queryset.filter(year=year)
        if start_date:
            queryset = queryset.filter(payment_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(payment_date__lte=end_date)
        
        by_group = queryset.values('group_name').annotate(
            total_amount=Sum('amount_paid'),
            count=Count('id'),
            approved_amount=Sum('amount_paid', filter=Q(is_approved=True)),
            unapproved_amount=Sum('amount_paid', filter=Q(is_approved=False))
        ).order_by('group_name')
        
        by_year = queryset.values('year').annotate(
            total_amount=Sum('amount_paid'),
            count=Count('id')
        ).order_by('year')
        
        overall = queryset.aggregate(
            total_amount=Sum('amount_paid'),
            total_count=Count('id'),
            approved_count=Count('id', filter=Q(is_approved=True)),
            unapproved_count=Count('id', filter=Q(is_approved=False))
        )
        
        return Response({
            'by_group': by_group,
            'by_year': by_year,
            'overall': overall,
            'filters': {
                'year': year,
                'start_date': start_date,
                'end_date': end_date
            }
        })
    
    @swagger_auto_schema(
        operation_description="Get all unapproved contributions for review",
        responses={200: ContributionListSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def unapproved(self, request):
        """View contributions awaiting priest approval"""
        return super().unapproved(request)
    
    @swagger_auto_schema(
        operation_description="Get contributions by specific group with stats",
        manual_parameters=[
            openapi.Parameter('group', openapi.IN_PATH, description="Group name (men, women, youth, children)", type=openapi.TYPE_STRING),
            openapi.Parameter('year', openapi.IN_QUERY, description="Filter by year", type=openapi.TYPE_INTEGER),
        ]
    )
    @action(detail=False, methods=['get'], url_path='by-group/(?P<group>[^/.]+)')
    def by_group(self, request, group=None):
        """Get contributions filtered by group"""
        queryset = self.queryset.filter(group_name=group)
        
        year = request.query_params.get('year')
        if year:
            queryset = queryset.filter(year=year)
        
        stats = queryset.aggregate(
            total_amount=Sum('amount_paid'),
            total_count=Count('id'),
            approved_count=Count('id', filter=Q(is_approved=True))
        )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ContributionListSerializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['statistics'] = stats
            return response
        
        serializer = ContributionListSerializer(queryset, many=True)
        return Response({
            'contributions': serializer.data,
            'statistics': stats
        })
    
    @swagger_auto_schema(
        operation_description="Search contributions by payer name (partial match)",
        manual_parameters=[
            openapi.Parameter('q', openapi.IN_QUERY, description="Search term for payer name", type=openapi.TYPE_STRING),
        ]
    )
    @action(detail=False, methods=['get'])
    def search(self, request):
        """Enhanced search with fuzzy matching"""
        query = request.query_params.get('q', '')
        if not query:
            return Response(
                {'error': 'Search query required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        queryset = self.queryset.filter(
            Q(payer_name__icontains=query) |
            Q(notes__icontains=query)
        )
        
        summary = queryset.aggregate(
            total_amount=Sum('amount_paid'),
            count=Count('id'),
            years=Count('year', distinct=True)
        )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ContributionListSerializer(page, many=True)
            response = self.get_paginated_response(serializer.data)
            response.data['search_summary'] = summary
            return response
        
        serializer = ContributionListSerializer(queryset, many=True)
        return Response({
            'results': serializer.data,
            'search_summary': summary
        })
    
    @swagger_auto_schema(
        operation_description="Get contributions that haven't been added to any batch",
        responses={200: ContributionListSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def unbatched(self, request):
        """View contributions not yet in any approval batch"""
        return super().unbatched(request)


class ContributionBatchViewSet(BaseApprovalBatchViewSet):
    """
    ViewSet for Yearly Contribution approval batches.
    
    Workflow:
    1. Secretary creates batch with unapproved contributions
    2. Priest reviews and approves/rejects batch
    3. Secretary hands over physical money to priest
    4. System tracks the financial flow
    """
    read_serializer_class = ContributionBatchReadSerializer
    create_serializer_class = ContributionBatchCreateSerializer
    
    def get_queryset(self):
        """Filter batches - priests see all, secretaries see their own"""
        queryset = YearlyContributionApprovalBatch.objects.all()
        
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        date_from = self.request.query_params.get('date_from', None)
        if date_from:
            queryset = queryset.filter(created_at__gte=date_from)
        
        date_to = self.request.query_params.get('date_to', None)
        if date_to:
            queryset = queryset.filter(created_at__lte=date_to)
        
        if self.request.user.is_authenticated and self.request.user.is_secretary:
            queryset = queryset.filter(raised_by=self.request.user)
        
        return queryset
    
    @swagger_auto_schema(
        operation_description="Get batch with detailed financial breakdown",
        responses={200: ContributionBatchReadSerializer()}
    )
    @action(detail=True, methods=['get'])
    def financial_summary(self, request, pk=None):
        """Get detailed financial breakdown of a batch"""
        batch = self.get_object()
        
        group_breakdown = batch.items.values('group_name').annotate(
            total_amount=Sum('amount_paid'),
            count=Count('id')
        ).order_by('group_name')
        
        totals = batch.items.aggregate(
            total_amount=Sum('amount_paid'),
            total_count=Count('id'),
            approved_count=Count('id', filter=Q(is_approved=True))
        )
        
        return Response({
            'batch': ContributionBatchReadSerializer(batch, context={'request': request}).data,
            'financial': {
                'by_group': group_breakdown,
                'totals': totals,
                'money_remitted': batch.money_remitted,
                'discrepancy': (
                    (batch.money_remitted or 0) - (totals['total_amount'] or 0)
                )
            }
        })