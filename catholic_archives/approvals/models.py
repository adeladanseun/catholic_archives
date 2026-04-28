# approvals/models.py
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class ApprovalBatch(models.Model):
    """A batch of records that the priest reviews and approves together"""
    BATCH_TYPES = [
        ('YearlyContribution', 'Contributions'),
        ('mass_intention', 'Mass Intentions'),
        ('mixed', 'Mixed'),
    ]
    
    batch_type = models.CharField(max_length=20, choices=BATCH_TYPES)
    approved_by = models.CharField(max_length=100)  # Priest's name
    approved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    record_count = models.IntegerField(default=0)
    
    class Meta:
        db_table = 'approval_batches'
        ordering = ['-approved_at']
    
    def __str__(self):
        return f"Batch #{self.id} - {self.batch_type} ({self.record_count} records)"

class ApprovalItem(models.Model):
    """Links approved records to an approval batch"""
    batch = models.ForeignKey(ApprovalBatch, on_delete=models.CASCADE, related_name='items')
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        db_table = 'approval_items'
        unique_together = ['content_type', 'object_id']
    
    def __str__(self):
        return f"Batch #{self.batch_id} - {self.content_type.model} #{self.object_id}"