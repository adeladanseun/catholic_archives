# mass_intentions/views.py - Add Swagger documentation
from rest_framework import viewsets, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from .models import MassIntention
from .serializers import MassIntentionSerializer

class MassIntentionViewSet(viewsets.ModelViewSet):
    """
    Manage mass intentions and thanksgiving offerings.
    
    ## Intention Types
    - **Regular**: Multiples of 500 (e.g., 500 = 1 day, 1500 = 3 days)
    - **Thanksgiving**: Open thanksgiving during mass, minimum 3,500
    
    ## Features
    - Filter by mass date, intention type
    - Search by names or intention text
    - Daily and date-range summaries
    - Auto-calculates number of days for regular intentions
    """
    queryset = MassIntention.objects.all()
    serializer_class = MassIntentionSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['mass_date', 'intention_type', 'is_approved']
    search_fields = ['concerned_names', 'intention_text']
    ordering_fields = ['mass_date', 'amount', 'created_at']
    ordering = ['mass_date', '-created_at']
    
    @swagger_auto_schema(
        operation_description="Get mass intentions summary for a date range",
        manual_parameters=[
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format='date'),
        ]
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get mass intentions summary"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = self.get_queryset()
        if start_date:
            queryset = queryset.filter(mass_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(mass_date__lte=end_date)
        
        type_summary = queryset.values('intention_type').annotate(
            total_amount=Sum('amount'),
            count=Count('id')
        )
        
        daily_summary = queryset.values('mass_date').annotate(
            total_amount=Sum('amount'),
            count=Count('id')
        ).order_by('mass_date')
        
        total_summary = queryset.aggregate(
            total_amount=Sum('amount'),
            total_count=Count('id')
        )
        
        unapproved = queryset.filter(is_approved=False).aggregate(
            unapproved_amount=Sum('amount'),
            unapproved_count=Count('id')
        )
        
        return Response({
            'type_summary': type_summary,
            'daily_summary': daily_summary,
            'total_summary': total_summary,
            'unapproved': unapproved,
            'filters': {'start_date': start_date, 'end_date': end_date}
        })