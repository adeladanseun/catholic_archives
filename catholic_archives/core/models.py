from django.db import models
from django.contrib.auth.models import AbstractUser
# Create your models here.

class SystemSetting(models.Model):
    SETTING_TYPES = [
        ('boolean', 'Boolean'),
        ('integer', 'Integer'),
        ('string', 'String'),
    ]
    
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=255)
    setting_type = models.CharField(max_length=20, choices=SETTING_TYPES, default='boolean')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'system_settings'
    
    def __str__(self):
        return f"{self.key}: {self.value}"
    
    def get_value(self):
        if self.setting_type == 'boolean':
            return self.value.lower() == 'true'
        elif self.setting_type == 'integer':
            return int(self.value)
        return self.value

class GroupRate(models.Model):
    GROUP_CHOICES = [
        ('men', 'Men'),
        ('women', 'Women'),
        ('youth', 'Youth'),
        ('children', 'Children'),
    ]
    
    group_name = models.CharField(max_length=20, choices=GROUP_CHOICES)
    annual_amount = models.DecimalField(max_digits=10, decimal_places=2)
    effective_from = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'group_rates'
        ordering = ['-effective_from']
    
    def __str__(self):
        return f"{self.get_group_name_display()}: {self.annual_amount} (from {self.effective_from})"

class User(AbstractUser):
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('priest', 'Priest'),
        ('secretary', 'Secretary/Recorder'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='secretary')
    phone = models.CharField(max_length=20, blank=True)
    
    class Meta:
        db_table = 'users'
    
    def is_priest(self):
        return self.role == 'priest'
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_secretary(self):
        return self.role == 'secretary'

