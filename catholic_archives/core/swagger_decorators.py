from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

# Common parameters
token_param = openapi.Parameter(
    'Authorization',
    openapi.IN_HEADER,
    description="Token authentication: 'Token {your_token}'",
    type=openapi.TYPE_STRING,
    required=True,
    default='Token '
)

# Common responses
unauthorized_response = openapi.Response(
    description="Unauthorized - Invalid or missing token",
    examples={"application/json": {"detail": "Authentication credentials were not provided."}}
)

forbidden_response = openapi.Response(
    description="Forbidden - Insufficient permissions",
    examples={"application/json": {"detail": "You do not have permission to perform this action."}}
)

def document_endpoint(summary, description, tags=None, manual_parameters=None):
    """Standard decorator for API documentation"""
    return swagger_auto_schema(
        operation_summary=summary,
        operation_description=description,
        tags=tags or ['Church Management'],
        manual_parameters=manual_parameters or [token_param],
        responses={
            200: 'Success',
            401: unauthorized_response,
            403: forbidden_response,
        }
    )