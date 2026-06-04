from datetime import datetime, timedelta

from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Sum, Count, Q
from django.utils import timezone

from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import exceptions

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import MassIntention, MassIntentionReading, MassIntentionApprovalBatch
from .serializers import (
    MassIntentionSerializer,
    MassIntentionListSerializer,
    MassIntentionBatchReadSerializer,
    MassIntentionBatchCreateSerializer,
)
from core.permissions import *
from core.views import GenericModelViewSet
from approvals.views import BaseApprovalBatchViewSet


class MassIntentionViewSet(GenericModelViewSet):
    """
    ViewSet for managing mass intentions.
    
    Types & Pricing:
    - Regular Intention: ₦500 per mass day
    - Open Thanksgiving: ₦3,000 minimum
    - Combined (Both): ₦3,500+ (Thanksgiving ₦3,000 + Regular ₦500 per mass day)
    
    Features:
    - Auto-calculate mass days based on church schedule
    - Separate thanksgiving date from regular announcement dates
    - Track actual readings with MassIntentionReading
    - Filter by mass date, thanksgiving date, type, approval status
    - Weekly/Monthly summaries
    - Mass schedule view with actual dates
    """
    queryset = MassIntention.objects.all()
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = [
        'mass_date', 
        'thanksgiving_date',
        'intention_type', 
        'is_approved', 
        'batch'
    ]
    search_fields = ['concerned_names', 'intention_text']
    ordering_fields = ['mass_date', 'thanksgiving_date', 'amount_paid', 'number_of_days', 'created_at']
    ordering = ['mass_date', '-created_at']

    list_serializer = MassIntentionListSerializer
    regular_serializer = MassIntentionSerializer
    
    def perform_create(self, serializer):
        """Set recorder - calculations handled in model.save()"""
        serializer.save(recorder=self.request.user)
    
    @swagger_auto_schema(
        operation_description="Get mass intentions with full mass date schedules",
        manual_parameters=[
            openapi.Parameter('date', openapi.IN_QUERY, description="Filter by mass start date or thanksgiving date (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('start_date', openapi.IN_QUERY, description="Start date for range", type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('end_date', openapi.IN_QUERY, description="End date for range", type=openapi.TYPE_STRING, format='date'),
        ],
        responses={200: MassIntentionListSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def by_date(self, request):
        """Get intentions for a specific date or range"""
        date_str = request.query_params.get('date')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = self.get_queryset()
        
        if date_str:
            queryset = queryset.filter(
                Q(mass_date=date_str) | Q(thanksgiving_date=date_str)
            )
        else:
            if start_date:
                queryset = queryset.filter(
                    Q(mass_date__gte=start_date) | Q(thanksgiving_date__gte=start_date)
                )
            if end_date:
                queryset = queryset.filter(
                    Q(mass_date__lte=end_date) | Q(thanksgiving_date__lte=end_date)
                )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.list_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.list_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @swagger_auto_schema(
        operation_description="Get mass schedule showing all announcement dates",
        manual_parameters=[
            openapi.Parameter('date', openapi.IN_QUERY, description="Filter by date (YYYY-MM-DD)", type=openapi.TYPE_STRING, format='date'),
        ]
    )
    @action(detail=False, methods=['get'], url_path='schedule')
    def mass_schedule(self, request):
        """Get complete mass schedule with calculated announcement dates"""
        date_str = request.query_params.get('date')
        
        queryset = self.get_queryset()
        if date_str:
            queryset = queryset.filter(
                Q(mass_date=date_str) | Q(thanksgiving_date=date_str)
            )
        
        schedule = {}
        for intention in queryset:
            try:
                announcement = intention.get_announcement_schedule()
                
                if intention.has_regular():
                    for mass_date in announcement.get('mass_dates', []):
                        date_key = str(mass_date)
                        if date_key not in schedule:
                            schedule[date_key] = {
                                'date': date_key,
                                'regular_intentions': [],
                                'thanksgivings': [],
                                'total_intentions': 0
                            }
                        
                        schedule[date_key]['regular_intentions'].append({
                            'id': intention.id,
                            'names': intention.concerned_names,
                            'text': intention.intention_text,
                            'type': intention.intention_type,
                            'amount': str(intention.amount_paid),
                            'day_number': announcement.get('mass_dates', []).index(mass_date) + 1
                        })
                        schedule[date_key]['total_intentions'] += 1
                
                if intention.has_thanksgiving() and intention.thanksgiving_date:
                    thanks_key = str(intention.thanksgiving_date)
                    if thanks_key not in schedule:
                        schedule[thanks_key] = {
                            'date': thanks_key,
                            'regular_intentions': [],
                            'thanksgivings': [],
                            'total_intentions': 0
                        }
                    
                    schedule[thanks_key]['thanksgivings'].append({
                        'id': intention.id,
                        'names': intention.concerned_names,
                        'text': intention.intention_text,
                        'type': intention.intention_type,
                        'amount': str(intention.amount_paid)
                    })
                    schedule[thanks_key]['total_intentions'] += 1
                    
            except Exception:
                continue
        
        sorted_schedule = dict(sorted(schedule.items()))
        
        return Response({
            'schedule': sorted_schedule,
            'total_dates': len(sorted_schedule),
            'filter_date': date_str
        })
    
    @swagger_auto_schema(
        operation_description="Mark an intention as read or skipped on a specific date",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['scheduled_date', 'was_read'],
            properties={
                'scheduled_date': openapi.Schema(type=openapi.TYPE_STRING, format='date', description='Date of the reading'),
                'was_read': openapi.Schema(type=openapi.TYPE_BOOLEAN, description='Whether the intention was read'),
                'skipped_reason': openapi.Schema(type=openapi.TYPE_STRING, description='Reason if skipped (e.g., mass canceled)'),
            }
        ),
        responses={
            200: "Reading recorded",
            400: "Validation error"
        }
    )
    @action(detail=True, methods=['post'], url_path='record-reading')
    def record_reading(self, request, pk=None):
        """Record whether an intention was read or skipped on a scheduled date"""
        instance = self.get_object()
        
        scheduled_date = request.data.get('scheduled_date')
        was_read = request.data.get('was_read', True)
        skipped_reason = request.data.get('skipped_reason', '')
        
        if not scheduled_date:
            return Response(
                {'error': 'scheduled_date is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not was_read and not skipped_reason:
            return Response(
                {'error': 'skipped_reason is required when was_read is false'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        reading, created = MassIntentionReading.objects.update_or_create(
            mass_intention=instance,
            scheduled_date=scheduled_date,
            defaults={
                'was_read': was_read,
                'skipped_reason': skipped_reason if not was_read else '',
                'read_by': request.user
            }
        )
        
        return Response({
            'message': 'Reading recorded successfully',
            'reading': {
                'scheduled_date': str(reading.scheduled_date),
                'was_read': reading.was_read,
                'skipped_reason': reading.skipped_reason,
                'days_left': instance.days_left,
                'readings_completed': instance.readings_completed
            }
        })
    
    @swagger_auto_schema(
        operation_description="Get reading status for an intention",
        responses={200: "Reading status"}
    )
    @action(detail=True, methods=['get'], url_path='reading-status')
    def reading_status(self, request, pk=None):
        """Get detailed reading status including days left and completion"""
        instance = self.get_object()
        
        if not instance.has_regular():
            return Response({
                'has_regular': False,
                'message': 'Thanksgiving-only intentions do not have multiple readings'
            })
        
        scheduled_dates = instance.calculate_mass_dates()
        readings = instance.readings.all()
        read_dates = {
            str(r.scheduled_date): {
                'was_read': r.was_read,
                'skipped_reason': r.skipped_reason,
                'read_by': str(r.read_by) if r.read_by else None
            }
            for r in readings
        }
        
        reading_list = []
        for d in scheduled_dates:
            date_str = str(d)
            reading_list.append({
                'date': date_str,
                'day_name': d.strftime('%A'),
                'status': 'read' if date_str in read_dates and read_dates[date_str]['was_read']
                          else 'skipped' if date_str in read_dates
                          else 'pending',
                'details': read_dates.get(date_str)
            })
        
        return Response({
            'intention_id': instance.id,
            'concerned_names': instance.concerned_names,
            'readings': reading_list,
            'days_left': instance.days_left,
            'readings_completed': instance.readings_completed
        })
    
    @swagger_auto_schema(
        operation_description="Get all intentions for next Sunday (the main thanksgiving day)",
        responses={200: MassIntentionListSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def next_sunday(self, request):
        """Get all intentions for next Sunday including thanksgivings"""
        today = datetime.now().date()
        days_until_sunday = (6 - today.weekday()) % 7
        if days_until_sunday == 0:
            days_until_sunday = 7
        
        next_sunday = today + timedelta(days=days_until_sunday)
        
        queryset = self.get_queryset().filter(
            Q(mass_date=next_sunday) | 
            Q(thanksgiving_date=next_sunday)
        )
        
        regular_intentions = []
        thanksgiving_intentions = []
        
        for intention in queryset:
            data = self.list_serializer(intention).data
            
            if intention.has_regular():
                mass_dates = intention.calculate_mass_dates()
                if next_sunday in mass_dates:
                    day_number = mass_dates.index(next_sunday) + 1
                    data['announcement_day'] = day_number
                    regular_intentions.append(data)
            
            if intention.has_thanksgiving() and intention.thanksgiving_date == next_sunday:
                data['is_thanksgiving_mass'] = True
                thanksgiving_intentions.append(data)
        
        return Response({
            'mass_date': str(next_sunday),
            'day_of_week': 'Sunday',
            'regular_intentions': regular_intentions,
            'thanksgiving_intentions': thanksgiving_intentions,
            'total_regular': len(regular_intentions),
            'total_thanksgivings': len(thanksgiving_intentions),
            'total_amount': queryset.aggregate(total=Sum('amount_paid'))['total'] or 0
        })
    
    @swagger_auto_schema(
        operation_description="Get this week's mass schedule with all announcement dates",
        responses={200: MassIntentionListSerializer(many=True)}
    )
    @action(detail=False, methods=['get'])
    def this_week(self, request):
        """Get complete schedule for the current week"""
        today = datetime.now().date()
        
        days_since_sunday = today.weekday() + 1
        if days_since_sunday == 7:
            sunday = today
            saturday = today + timedelta(days=6)
        else:
            sunday = today - timedelta(days=days_since_sunday)
            saturday = sunday + timedelta(days=6)
        
        queryset = self.get_queryset().filter(
            Q(mass_date__lte=saturday) &
            (Q(end_date__gte=sunday) | Q(end_date__isnull=True))
        ) | self.get_queryset().filter(
            thanksgiving_date__gte=sunday,
            thanksgiving_date__lte=saturday
        )
        
        daily_schedule = {}
        current_date = sunday
        while current_date <= saturday:
            date_key = str(current_date)
            daily_schedule[date_key] = {
                'date': date_key,
                'day_name': current_date.strftime('%A'),
                'intentions': [],
                'thanksgivings': [],
                'total_intentions': 0
            }
            
            for intention in queryset:
                schedule_info = intention.get_announcement_schedule()
                
                if intention.has_regular():
                    mass_dates = schedule_info.get('mass_dates', [])
                    if current_date in mass_dates:
                        daily_schedule[date_key]['intentions'].append({
                            'id': intention.id,
                            'names': intention.concerned_names,
                            'type': intention.intention_type,
                            'text': intention.intention_text
                        })
                        daily_schedule[date_key]['total_intentions'] += 1
                
                if intention.has_thanksgiving() and intention.thanksgiving_date == current_date:
                    daily_schedule[date_key]['thanksgivings'].append({
                        'id': intention.id,
                        'names': intention.concerned_names,
                        'type': intention.intention_type,
                        'text': intention.intention_text
                    })
                    daily_schedule[date_key]['total_intentions'] += 1
            
            current_date += timedelta(days=1)
        
        return Response({
            'week_info': {
                'start_date': str(sunday),
                'end_date': str(saturday)
            },
            'daily_schedule': daily_schedule,
            'totals': {
                'total_intentions_this_week': queryset.count(),
                'total_amount': queryset.aggregate(total=Sum('amount_paid'))['total'] or 0
            }
        })
    
    @swagger_auto_schema(
        operation_description="Get intention with full announcement schedule",
        responses={200: MassIntentionSerializer()}
    )
    @action(detail=True, methods=['get'])
    def full_schedule(self, request, pk=None):
        """Get single intention with its complete announcement schedule"""
        instance = self.get_object()
        serializer = self.regular_serializer(instance)
        
        data = serializer.data
        data['schedule'] = instance.get_announcement_schedule()
        data['days_left'] = instance.days_left
        data['readings_completed'] = instance.readings_completed
        
        return Response(data)
    
    @swagger_auto_schema(
        operation_description="Get all thanksgivings for a specific date or range",
        manual_parameters=[
            openapi.Parameter('date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format='date'),
        ]
    )
    @action(detail=False, methods=['get'], url_path='thanksgiving-schedule')
    def thanksgiving_schedule(self, request):
        """Get thanksgiving schedule for a date range"""
        date_str = request.query_params.get('date')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = self.get_queryset().filter(
            Q(intention_type=MassIntention.THANKSGIVING) |
            Q(intention_type=MassIntention.BOTH)
        )
        
        if date_str:
            queryset = queryset.filter(thanksgiving_date=date_str)
        else:
            if start_date:
                queryset = queryset.filter(thanksgiving_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(thanksgiving_date__lte=end_date)
        
        schedule = {}
        for intention in queryset:
            if intention.thanksgiving_date:
                date_key = str(intention.thanksgiving_date)
                if date_key not in schedule:
                    schedule[date_key] = []
                schedule[date_key].append({
                    'id': intention.id,
                    'names': intention.concerned_names,
                    'text': intention.intention_text,
                    'type': intention.intention_type,
                    'amount': str(intention.amount_paid)
                })
        
        sorted_schedule = dict(sorted(schedule.items()))
        
        stats = queryset.aggregate(
            total_amount=Sum('amount_paid'),
            total_count=Count('id'),
            pure_thanksgiving=Count('id', filter=Q(intention_type=MassIntention.THANKSGIVING)),
            combined=Count('id', filter=Q(intention_type=MassIntention.BOTH))
        )
        
        return Response({
            'thanksgiving_schedule': sorted_schedule,
            'statistics': stats
        })
    
    @swagger_auto_schema(
        operation_description="Get summary with scheduling information",
        manual_parameters=[
            openapi.Parameter('start_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format='date'),
            openapi.Parameter('end_date', openapi.IN_QUERY, type=openapi.TYPE_STRING, format='date'),
        ]
    )
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get comprehensive summary with schedule information"""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = self.get_queryset()
        if start_date:
            queryset = queryset.filter(mass_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(mass_date__lte=end_date)
        
        by_type = queryset.values('intention_type').annotate(
            total_amount=Sum('amount_paid'),
            count=Count('id'),
            total_mass_days=Sum('number_of_days')
        ).order_by('intention_type')
        
        thanksgiving_stats = queryset.filter(
            Q(intention_type=MassIntention.THANKSGIVING) |
            Q(intention_type=MassIntention.BOTH)
        ).aggregate(
            total_thanksgivings=Count('id'),
            total_thanksgiving_amount=Sum('amount_paid'),
            unique_thanksgiving_dates=Count('thanksgiving_date', distinct=True)
        )
        
        regular_stats = queryset.filter(
            Q(intention_type=MassIntention.REGULAR) |
            Q(intention_type=MassIntention.BOTH)
        ).aggregate(
            total_regular=Count('id'),
            total_regular_amount=Sum('amount_paid'),
            total_announcement_days=Sum('number_of_days')
        )
        
        totals = queryset.aggregate(
            total_amount=Sum('amount_paid'),
            total_count=Count('id'),
            approved_count=Count('id', filter=Q(is_approved=True)),
            unapproved_count=Count('id', filter=Q(is_approved=False)),
            total_mass_days=Sum('number_of_days')
        )
        
        return Response({
            'by_type': by_type,
            'thanksgiving_breakdown': thanksgiving_stats,
            'regular_breakdown': regular_stats,
            'totals': totals,
            'filters': {
                'start_date': start_date,
                'end_date': end_date
            }
        })


class MassIntentionBatchViewSet(BaseApprovalBatchViewSet):
    """
    ViewSet for Mass Intention approval batches.
    
    Workflow:
    1. Secretary collects mass intention payments
    2. Creates a batch with multiple intentions
    3. Priest reviews, verifies amounts, and approves
    4. Intentions are scheduled for announced masses
    """
    read_serializer_class = MassIntentionBatchReadSerializer
    create_serializer_class = MassIntentionBatchCreateSerializer
    
    def get_queryset(self):
        """Filter batches - show upcoming masses first"""
        queryset = MassIntentionApprovalBatch.objects.all()
        
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
        
        return queryset.order_by('-created_at')
    
    @swagger_auto_schema(
        operation_description="Get batch with upcoming mass schedule",
        responses={200: MassIntentionBatchReadSerializer()}
    )
    @action(detail=True, methods=['get'])
    def schedule(self, request, pk=None):
        """View the mass schedule for intentions in this batch"""
        batch = self.get_object()
        
        schedule = {}
        for intention in batch.items.all().order_by('mass_date'):
            date_key = str(intention.mass_date)
            if date_key not in schedule:
                schedule[date_key] = {
                    'date': date_key,
                    'intentions': [],
                    'total_intentions': 0,
                    'thanksgivings': 0,
                    'total_amount': 0,
                    'total_days': 0
                }
            
            schedule[date_key]['intentions'].append({
                'id': intention.id,
                'names': intention.concerned_names,
                'text': intention.intention_text,
                'type': intention.intention_type,
                'amount': str(intention.amount_paid),
                'days': intention.number_of_days
            })
            schedule[date_key]['total_intentions'] += 1
            schedule[date_key]['total_amount'] += intention.amount_paid
            schedule[date_key]['total_days'] += intention.number_of_days
            
            if intention.intention_type == 'thanksgiving':
                schedule[date_key]['thanksgivings'] += 1
        
        return Response({
            'batch': MassIntentionBatchReadSerializer(batch, context={'request': request}).data,
            'mass_schedule': list(schedule.values()),
            'summary': {
                'total_masses': len(schedule),
                'total_intentions': batch.items.count(),
                'total_thanksgivings': batch.items.filter(intention_type=MassIntention.THANKSGIVING).count(),
                'total_amount': batch.items.aggregate(total=Sum('amount_paid'))['total'] or 0
            }
        })