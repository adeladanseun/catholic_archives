# contributions/views.py - Add Swagger documentation
from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import YearlyContribution
from .serializers import ContributionSerializer, ContributionListSerializer

class ContributionViewSet(viewsets.ModelViewSet):
    """
    Manage yearly church contributions.
    
    ## Permissions
    - **Secretary**: Can create, view, update, and delete contributions
    - **Priest/Admin**: Full access including approval
    
    ## Features
    - Filter by year, group name, payment date
    - Search by payer name or serial number
    - Summary reports by year/group
    - View unapproved records
    """
    queryset = YearlyContribution.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['year', 'group_name', 'is_approved', 'payment_date']
    search_fields = ['payer_name', 'serial_number']
    ordering_fields = ['payment_date', 'amount_paid', 'created_at']
    ordering = ['-payment_date']
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ContributionListSerializer
        return ContributionSerializer
    
    @swagger_auto_schema(
        operation_description="Get contribution summary grouped by category",
        manual_parameters=[
            openapi.Parameter(
                'year', openapi.IN_QUERY, 
                description="Filter by year (e.g., 2024)", 
                type=openapi.TYPE_INTEGER
            ),
        ],
        responses={
            200: openapi.Response(
                description="Summary data",
                examples={
                    "application/json": {
                        "group_summary": [
                            {"group_name": "men", "total_amount": "50000", "count": 50}
                        ],
                        "total_summary": {"total_amount": "150000", "total_count": 300},
                        "unapproved": {"unapproved_amount": "25000", "unapproved_count": 25}
                    }
                }
            )
        }
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get financial summary of contributions"""
        year = request.query_params.get('year')
        queryset = self.get_queryset()
        
        if year:
            queryset = queryset.filter(year=year)
        
        group_summary = queryset.values('group_name').annotate(
            total_amount=Sum('amount_paid'),
            count=Count('id')
        ).order_by('group_name')
        
        total_summary = queryset.aggregate(
            total_amount=Sum('amount_paid'),
            total_count=Count('id')
        )
        
        unapproved = queryset.filter(is_approved=False).aggregate(
            unapproved_amount=Sum('amount_paid'),
            unapproved_count=Count('id')
        )
        
        return Response({
            'group_summary': group_summary,
            'total_summary': total_summary,
            'unapproved': unapproved,
            'filters': {'year': year}
        })
    
    @swagger_auto_schema(
        operation_description="Get all unapproved contributions for priest review",
        responses={200: ContributionListSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def unapproved(self, request):
        """Get unapproved contributions"""
        queryset = self.queryset.filter(is_approved=False)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)