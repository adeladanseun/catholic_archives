# church_api/urls.py - Updated
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.permissions import AllowAny
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

from yearly_contributions.views import ContributionViewSet, ContributionBatchViewSet
from mass_intentions.views import MassIntentionViewSet, MassIntentionBatchViewSet
from approvals.views import BaseApprovalBatchViewSet  # Generic if still needed
from core.views import (
    SystemSettingViewSet, GroupRateViewSet, UserViewSet,
    UserRegistrationView, LoginView, LogoutView
)

# Main API Router
router = DefaultRouter()
router.register(r'contributions', ContributionViewSet, basename='contribution')
router.register(r'contribution-batches', ContributionBatchViewSet, basename='contribution-batch')
router.register(r'mass-intentions', MassIntentionViewSet, basename='mass-intention')
router.register(r'mass-intention-batches', MassIntentionBatchViewSet, basename='mass-intention-batch')
router.register(r'settings', SystemSettingViewSet, basename='settings')
router.register(r'group-rates', GroupRateViewSet, basename='group-rate')
router.register(r'users', UserViewSet, basename='user')

# Schema View for Swagger
schema_view = get_schema_view(
    openapi.Info(
        title="Church Management API",
        default_version='v1',
        description="""
        Comprehensive API for church financial management.
        
        ## Core Features
        - **Yearly Contributions**: Track member contributions by group
        - **Mass Intentions**: Manage mass intentions and thanksgivings
        - **Approval Workflow**: Priest review and batch approval
        - **Financial Reports**: Detailed summaries and statistics
        
        ## Authentication
        1. Register/Login to get your token
        2. Use `Authorization: Token <your_token>` header
        3. Role-based access control
        
        ## User Roles
        - **Priest**: Approve batches, view all records
        - **Secretary**: Record contributions and intentions
        - **Admin**: Full system management
        """,
        contact=openapi.Contact(email="admin@church.com"),
    ),
    public=True,
    permission_classes=[AllowAny],
)

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
    
    # API Documentation
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    
    # Authentication
    path('api/auth/register/', UserRegistrationView.as_view(), name='auth-register'),
    path('api/auth/login/', LoginView.as_view(), name='auth-login'),
    path('api/auth/logout/', LogoutView.as_view(), name='auth-logout'),
    
    # Main API endpoints
    path('api/', include(router.urls)),
]