from django.db import models
from django.contrib.auth import get_user_model
from approvals.models import ApprovalItem, ApprovalBatch

# Create your models here.

class YearlyContributionApprovalBatch(ApprovalBatch):
    pass

class YearlyContribution(ApprovalItem):
    GROUP_CHOICES = [
        ('men', 'Men'),
        ('women', 'Women'),
        ('youth', 'Youth'),
        ('children', 'Children'),
    ]
    
    batch = models.ForeignKey(YearlyContributionApprovalBatch, on_delete=models.SET_NULL, related_name='items', null=True)
    #serial_number = models.CharField(max_length=50, unique=True)
    payer_name = models.CharField(max_length=255, help_text="Can be individual or group name")
    group_name = models.CharField(max_length=20, choices=GROUP_CHOICES)
    year = models.IntegerField()
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField()
    notes = models.TextField(blank=True)
    
    
    class Meta:
        db_table = 'yearly_contributions'
        ordering = ['-payment_date', '-created_at']
        indexes = [
            models.Index(fields=['year', 'group_name']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['payer_name']),
        ]
    
    def __str__(self):
        return f"{self.serial_number} - {self.payer_name} ({self.year})"
