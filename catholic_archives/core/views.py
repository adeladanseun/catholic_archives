from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.authtoken.models import Token

from django.contrib.auth import authenticate, get_user_model
from django.utils.dateparse import parse_date

from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import SystemSetting, GroupRate
from .serializers import (
    SystemSettingSerializer, GroupRateSerializer,
    UserSerializer, UserRegistrationSerializer, LoginSerializer
)
from .permissions import IsPriestUser, IsAdminOrPriest

User = get_user_model()

class UserRegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = [IsAdminOrPriest]
    serializer_class = UserRegistrationSerializer
    
    def get_queryset(self):
        return User.objects.all()
    
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
    - **priest/priest**: Priest account for approvals
    - **secretary/secretary**: Daily data entry
    - **admin/admin**: Full system access
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
                password=serialilzer.validated_data['password']
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
        # Delete the user's token to logout
        Token.objects.filter(user=request.user).delete()
        return Response({'message': 'Successfully logged out'})

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrPriest]  # Only admin and priest can manage users
    
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