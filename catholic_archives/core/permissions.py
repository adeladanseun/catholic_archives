# core/permissions.py - New file
from rest_framework import permissions

class IsPriestUser(permissions.BasePermission):
    """
    Permission for priest-only actions (approving records)
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_priest()

class IsAdminOrPriest(permissions.BasePermission):
    """
    Permission for admin or priest actions
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_admin() or request.user.is_priest()
        )

class IsAdmin(permissions.BasePermission):
    """
    Permission for admin actions
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_admin()
        )
class IsSecretary(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_secretary

class IsAuthenticated(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated
class IsSecretaryOrAbove(permissions.BasePermission):
    """
    Permission for data entry (secretary, priest, or admin)
    """
    def has_permission(self, request, view):
        return request.user.is_authenticated

class ReadOnlyForPriest(permissions.BasePermission):
    """
    Priests can view everything but only create approvals
    """
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        
        if request.user.is_priest():
            return request.method in permissions.SAFE_METHODS
        
        return True  # Secretary and admin can do everything