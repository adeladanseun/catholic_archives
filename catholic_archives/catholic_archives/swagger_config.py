# church_api/swagger_config.py - New file
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions
from django.conf import settings

# API Info for documentation
api_info = openapi.Info(
    title="Church Management API",
    default_version='v1',
    description="""
    API for managing church contributions, mass intentions, and priest approvals.
    
    ## Authentication
    All endpoints (except login/register) require token authentication.
    
    1. **Get your token**: POST to `/api/auth/login/` with your credentials
    2. **Use the token**: Add header `Authorization: Token {your_token}`
    
    ## User Roles
    - **Priest**: Can view all records and approve batches
    - **Secretary**: Can record contributions and mass intentions
    - **Admin**: Full access to all features
    
    ## Key Workflows
    1. Secretary records contributions and intentions daily
    2. Priest reviews pending records remotely
    3. Priest approves in batches
    4. Reports available for financial tracking
    """,
    contact=openapi.Contact(email="admin@church.com"),
    license=openapi.License(name="Private Use"),
    terms_of_service="https://www.church.com/terms/",
)

# Schema view configuration
schema_view = get_schema_view(
    api_info,
    public=True,
    permission_classes=[permissions.AllowAny],
    authentication_classes=[
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
)