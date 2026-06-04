from django.db import models
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import DateModel


class ApprovalBatch(DateModel):
    """A batch of records that the priest reviews and approves together"""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    raised_by = models.ForeignKey(
        get_user_model(), 
        related_name="requested_%(class)s_approvals", 
        on_delete=models.SET_NULL, 
        null=True
    )
    approved_by = models.ForeignKey(
        get_user_model(), 
        related_name="approved_%(class)s_batches", 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    notes = models.TextField(blank=True)
    money_remitted = models.BooleanField(default=False)
    rejection_reason = models.TextField(blank=True)
    rejected_by = models.ForeignKey(
        get_user_model(),
        related_name="rejected_%(class)s_batches",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    rejected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        abstract = True
        ordering = ['-approved_at', '-created_at']
    
    def __str__(self):
        return f"Batch #{self.id} - ({self.record_count} records)"

    @property
    def record_count(self):
        return self.items.count()

    @property
    def total_amount(self):
        amount = 0
        for item in self.items.all():
            amount += item.amount_paid
        return amount

    @property
    def is_approved(self):
        return self.status == 'approved' and self.approved_by is not None

    @property
    def is_rejected(self):
        return self.status == 'rejected'

    def approve_batch(self, approved_by):
        """Approve all items in this batch"""
        if not self.money_remitted:
            raise ValidationError("The money has not been remitted yet")
        
        if self.is_approved:
            raise ValidationError("Batch is already approved")
        
        now = timezone.now()
        self.status = 'approved'
        self.approved_by = approved_by
        self.approved_at = now
        self.save()
        
        # Approve all items
        for item in self.items.all():
            item.approve(approved_by=approved_by, approved_at=now)

    def reject_batch(self, rejected_by, reason=''):
        """Reject batch and unlink all items"""
        if self.is_approved:
            raise ValidationError("Cannot reject an approved batch")
        
        now = timezone.now()
        self.status = 'rejected'
        self.rejected_by = rejected_by
        self.rejected_at = now
        self.rejection_reason = reason
        self.save()
        
        # Unlink items and reset approval status
        self.items.update(
            batch=None,
            is_approved=False,
            approved_by=None,
            approved_at=None
        )


class ApprovalItem(DateModel):
    """Links approved records to an approval batch"""
    recorder = models.ForeignKey(
        get_user_model(), 
        related_name='recorded_%(class)s', 
        on_delete=models.SET_NULL, 
        null=True
    )
    # Approval fields
    is_approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey(
        get_user_model(), 
        related_name='approved_%(class)s', 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True
    )
    approved_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        abstract = True

    def approve(self, approved_by=None, approved_at=None):
        """Mark the linked record as approved"""
        if approved_by and approved_at:
            self.is_approved = True
            self.approved_by = approved_by
            self.approved_at = approved_at
            self.save()
        else:
            raise ValueError("Object does not support approval or approved_by is missing")

    @property
    def is_awaiting_approval(self):
        return self.batch is not None