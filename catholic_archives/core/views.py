from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework import exceptions

from django.contrib.auth import authenticate, get_user_model
from django.utils.dateparse import parse_date
from django.utils import timezone

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import SystemSetting, GroupRate
from .serializers import (
    SystemSettingSerializer, GroupRateSerializer,
    UserSerializer, UserRegistrationSerializer, LoginSerializer
)
from .permissions import *

User = get_user_model()


class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [IsAdminOrPriest]
    serializer_class = UserRegistrationSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Create token for new user
        token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    """
    Authenticate and receive a token for API access.
    
    ## User Roles:
    - **priest**: Priest account for approvals
    - **secretary**: Daily data entry
    - **admin**: Full system access
    """
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer
    
    @swagger_auto_schema(
        operation_description="Login to get authentication token",
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['username', 'password'],
            properties={
                'username': openapi.Schema(type=openapi.TYPE_STRING, description='Your username'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, format='password', description='Your password'),
            }
        ),
        responses={
            200: openapi.Response(
                description="Successful login",
                examples={
                    "application/json": {
                        "user": {
                            "id": 2,
                            "username": "priest",
                            "role": "priest"
                        },
                        "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b",
                        "message": "Welcome Father Michael"
                    }
                }
            ),
            401: "Invalid credentials"
        }
    )
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        user = authenticate(
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password']
        ) or authenticate(
            email=serializer.validated_data['username'],
            password=serializer.validated_data['password']
        )
        
        if not user:
            return Response({
                'error': 'Invalid credentials'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        # Get or create token
        token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            'user': UserSerializer(user).data,
            'token': token.key,
            'message': f'Welcome Father {user.last_name}' if user.is_priest() else f'Welcome {user.first_name}'
        })


class LogoutView(generics.GenericAPIView):
    """Logout by deleting your token"""
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        operation_description="Logout and invalidate your token",
        responses={200: "Successfully logged out"}
    )
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response({'message': 'Successfully logged out'})


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrPriest]
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current logged-in user's profile"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class SystemSettingViewSet(viewsets.ModelViewSet):
    queryset = SystemSetting.objects.all()
    serializer_class = SystemSettingSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'key'
    
    def get_object(self):
        return SystemSetting.objects.get(key=self.kwargs['key'])


class GroupRateViewSet(viewsets.ModelViewSet):
    queryset = GroupRate.objects.all()
    serializer_class = GroupRateSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAdminOrPriest]
        return super().get_permissions()
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        date_str = request.query_params.get('date')
        if date_str:
            date = parse_date(date_str)
            rate = GroupRate.objects.filter(
                effective_from__lte=date
            ).order_by('-effective_from').first()
        else:
            rate = GroupRate.objects.order_by('-effective_from').first()
        
        if rate:
            serializer = self.get_serializer(rate)
            return Response(serializer.data)
        return Response({'error': 'No rate found'}, status=404)
    
    @action(detail=False, methods=['get'])
    def all_active(self, request):
        from django.db.models import Q, Max
        
        date_str = request.query_params.get('date')
        if date_str:
            date = parse_date(date_str)
            latest_dates = GroupRate.objects.filter(
                effective_from__lte=date
            ).values('group_name').annotate(max_date=Max('effective_from'))
        else:
            latest_dates = GroupRate.objects.values('group_name').annotate(
                max_date=Max('effective_from')
            )
        
        conditions = Q()
        for item in latest_dates:
            conditions |= Q(
                group_name=item['group_name'],
                effective_from=item['max_date']
            )
        
        rates = GroupRate.objects.filter(conditions)
        serializer = self.get_serializer(rates, many=True)
        return Response(serializer.data)


class GenericModelViewSet(viewsets.ModelViewSet):
    """
    Base ViewSet for models that need approval workflow.
    
    Features:
    - Prevents update/delete on approved records
    - Provides approve action for individual records
    - Provides unbatched and unapproved filters
    """

    def get_serializer_class(self):
        if self.action == 'list':
            return self.list_serializer
        return self.regular_serializer
    
    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [(IsSecretary | IsAdmin)]
        elif self.action in ['approve']:
            self.permission_classes = [(IsPriestUser | IsAdmin)]
        else:
            self.permission_classes = [IsAuthenticated]
        return [permission() for permission in self.permission_classes]
    
    def perform_update(self, serializer):
        """Prevent updating approved records"""
        if serializer.instance.is_approved:
            raise exceptions.PermissionDenied(
                f"Cannot update an approved {serializer.instance.__class__.__name__}."
            )
        serializer.save()
    
    def perform_destroy(self, instance):
        """Prevent deleting approved records"""
        if instance.is_approved:
            raise exceptions.PermissionDenied(
                f"Cannot delete an approved {instance.__class__.__name__}."
            )
        instance.delete()
    
    @action(detail=False, methods=['get'])
    def unbatched(self, request):
        """View instances not yet in any approval batch"""
        queryset = self.queryset.filter(batch__isnull=True)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.list_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.list_serializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(
        operation_description="Approve a single instance (Priest only)",
        responses={
            200: "Instance approved",
            403: "Permission denied"
        }
    )
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Priest approves an individual record directly"""
        if not request.user.is_priest and not request.user.is_staff:
            return Response(
                {'error': 'Only priests can approve'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        instance = self.get_object()
        if instance.is_approved:
            return Response(
                {'error': f'{instance.__class__.__name__} already approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        instance.is_approved = True
        instance.approved_by = request.user
        instance.approved_at = timezone.now()
        instance.save()
        
        return Response({
            'message': f'{instance.__class__.__name__} approved',
            f'{instance.__class__.__name__.lower()}': self.list_serializer(instance).data
        })

    @action(detail=False, methods=['get'])
    def unapproved(self, request):
        """View instances awaiting priest approval"""
        queryset = self.queryset.filter(is_approved=False)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.list_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = self.list_serializer(queryset, many=True)
        return Response(serializer.data)