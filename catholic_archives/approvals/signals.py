from django.db.models.signals import pre_delete
from django.core.exceptions import PermissionDenied
from django.dispatch import receiver
from .models import *

@receiver(pre_delete, sender=ApprovalItem)
def protect_approved_items(sender, instance, **kwargs):
    if instance.batch.is_approved: # Assuming a property or field name
        raise PermissionDenied("Protected: Batch is already approved.")

@receiver(pre_delete, sender=ApprovalBatch)
def protect_approved_batch(sender, instance, **kwargs):
    if instance.is_approved:
        raise PermissionDenied("Protected: Batch is already approved.")