# mass_intentions/models.py
from django.db import models
from django.core.validators import MinValueValidator

class MassIntention(models.Model):
    INTENTION_TYPE = [
        ('regular', 'Regular Intention'),
        ('thanksgiving', 'Open Thanksgiving'),
    ]
    
    mass_date = models.DateField()
    concerned_names = models.CharField(
        max_length=500, 
        help_text="Can be individual, group, or anonymous (e.g., 'The Choir', 'Mr and Mrs Obi')"
    )
    intention_text = models.TextField()
    intention_type = models.CharField(max_length=20, choices=INTENTION_TYPE)
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(500)]
    )
    number_of_days = models.IntegerField(default=1, help_text="Calculated for regular intentions")
    
    # Approval fields
    is_approved = models.BooleanField(default=False)
    approved_by = models.CharField(max_length=100, blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
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
            self.number_of_days = int(self.amount / 500)
        super().save(*args, **kwargs)
