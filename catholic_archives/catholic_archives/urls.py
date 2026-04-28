# church_api/urls.py
from django.contrib import admin
from django.urls import path, include, re_path
from rest_framework.routers import DefaultRouter
from rest_framework.permissions import AllowAny

# Swagger imports
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from django.conf import settings

from yearly_contributions.views import ContributionViewSet
from mass_intentions.views import MassIntentionViewSet
from approvals.views import ApprovalBatchViewSet
from core.views import (
    SystemSettingViewSet, GroupRateViewSet, UserViewSet,
    UserRegistrationView, LoginView, LogoutView
)

# API Router
router = DefaultRouter()
router.register(r'contributions', ContributionViewSet, basename='contribution')
router.register(r'mass-intentions', MassIntentionViewSet, basename='mass-intention')
router.register(r'settings', SystemSettingViewSet, basename='settings')
router.register(r'group-rates', GroupRateViewSet, basename='group-rate')
router.register(r'users', UserViewSet, basename='user')

# Schema View
schema_view = get_schema_view(
    openapi.Info(
        title="Church Management API",
        default_version='v1',
        description="""
        API for managing church contributions, mass intentions, and priest approvals.
        
        # Authentication
        All endpoints (except login/register) require token authentication.
        
        1. **Register/Login**: GET your token from `/api/auth/login/`
        2. **Use token**: Add header `Authorization: Token {your_token}`
        3. **Priest token**: Use priest credentials to access approval endpoints
        
        # User Roles & Permissions
        - **Priest**: View all records, approve batches
        - **Secretary**: Record contributions & mass intentions
        - **Admin**: Full system access
        
        # Key Features
        - Dynamic group rates with historical tracking
        - Amount validation (can be toggled)
        - Batch approval workflow for priest
        - Comprehensive reporting endpoints
        """,
        contact=openapi.Contact(email="admin@church.com"),
        license=openapi.License(name="Private"),
    ),
    public=True,
    permission_classes=[AllowAny],
    authentication_classes=[],
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
    
    # Approvals (separate for clarity)
    path('api/approvals/', include('approvals.urls')),
]