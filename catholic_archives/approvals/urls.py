from django.urls import path, include
from rest_framework.routers import DefaultRouter
#from .views import ApprovalBatchViewSet

router = DefaultRouter()
#router.register(r'batches', ApprovalBatchViewSet)

urlpatterns = [
    path('', include(router.urls)),
]