from django.db import models
from django.contrib.auth import get_user_model

from core.models import DateModel

class ApprovalBatchManager(models.Manager):
    def save(self, *args, **kwargs):
        old_batch = ApprovalBatch.objects.get(id=self.id)
        if (not old_batch.approved_by) and (self.approved_by):#wasnt previously approved and now approved
            if (not self.money_remitted):
                raise ValueError("The money has not been remitted yet")
            items = self.items.all()
            for item in items:
                item.approve(approved_by=self.approved_by, approved_at=self.approved_at)
            super().save(*args, **kwargs)

class ApprovalBatch(DateModel):
    """A batch of records that the priest reviews and approves together"""
    raised_by = models.ForeignKey(get_user_model(), related_name="requested_%(class)s_approvals", on_delete=models.SET_NULL, null=True)
    approved_by = models.ForeignKey(get_user_model(), related_name="approved_%(class)s_batches", on_delete=models.SET_NULL, null=True)  # Priest
    approved_at = models.DateTimeField()
    notes = models.TextField(blank=True)
    money_remitted = models.BooleanField(default=False)
    
    objects = ApprovalBatchManager()

    class Meta:
        abstract = True
        ordering = ['-approved_at', '-date_created']
    
    def __str__(self):
        return f"Batch #{self.id} - ({self.record_count} records)"

    @property
    def total_amount(self):
        amount = 0
        for item in self.items.all():
            amount += item.amount_paid
        return amount


class ApprovalItem(DateModel):#delete protected by signals.py
    """Links approved records to an approval batch"""
    recorder = models.ForeignKey(get_user_model(), related_name='recorded_%(class)s', on_delete=models.SET_NULL, null=True)
    # Approval fields
    is_approved = models.BooleanField(default=False)
    #approved_by = models.CharField(max_length=100, blank=True, null=True)
    approved_by = models.ForeignKey(get_user_model(), related_name='approved_%(class)s', on_delete=models.SET_NULL, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        abstract = True
    

    def approve(self, approved_by=None, approved_at=None):
        """Mark the linked record as approved"""
        if approved_by and approved_at:
            self.is_approved = True
            self.approved_by = approved_by
            self.approved_at = self.batch.approved_at#flag
            self.save()
        else:
            raise ValueError("Object does not support approval or approved_by is missing")

    @property
    def is_awaiting_approval(self):
        return self.batch #if it has a batch then it is awaiting approval