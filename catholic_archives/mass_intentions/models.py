from django.db import models
from django.core.validators import MinValueValidator
from approvals.models import ApprovalItem, ApprovalBatch


class MassIntentionApprovalBatch(ApprovalBatch):
    pass

class MassIntention(ApprovalItem):
    REGULAR = 'regular'
    THANKSGIVING = 'thanksgiving'

    INTENTION_TYPE = [
        (REGULAR, 'Regular Intention'),
        (THANKSGIVING, 'Open Thanksgiving'),
    ]
    batch = models.ForeignKey(MassIntentionApprovalBatch, on_delete=models.SET_NULL, related_name='items', null=True)
    mass_date = models.DateField()
    concerned_names = models.CharField(
        max_length=500, 
        help_text="Can be individual, group, or anonymous (e.g., 'The Choir', 'Mr and Mrs Obi')"
    )
    intention_text = models.TextField()
    intention_type = models.CharField(max_length=20, choices=INTENTION_TYPE)
    amount_paid = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(500)]
    )
    number_of_days = models.IntegerField(default=1, help_text="Calculated for regular intentions")
    
    
    class Meta:
        db_table = 'mass_intentions'
        ordering = ['mass_date', '-created_at']
        indexes = [
            models.Index(fields=['mass_date']),
            models.Index(fields=['intention_type']),
        ]
    
    def __str__(self):
        return f"{self.mass_date} - {self.concerned_names}: {self.intention_text[:50]}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate number of days for regular intentions
        if self.intention_type == 'regular' and self.amount:
            self.number_of_days = int(self.amount / 500)#get rate instead of using 500
        super().save(*args, **kwargs)
