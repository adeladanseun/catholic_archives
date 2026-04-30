from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth import get_user_model
# Create your models here.
class DateModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class SystemSetting(models.Model):
    BOOLEAN = 'boolean'
    INTEGER = 'integer'
    STRING = 'string'
    
    SETTING_TYPES = [
        (BOOLEAN, 'Boolean'),
        (INTEGER, 'Integer'),
        (STRING, 'String'),
    ]
    
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=255)
    setting_type = models.CharField(max_length=20, choices=SETTING_TYPES, default=BOOLEAN)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'system_settings'
    
    def __str__(self):
        return f"{self.key}: {self.value}"
    
    def get_value(self):
        if self.setting_type == BOOLEAN:
            return self.value.lower() == 'true'
        elif self.setting_type == INTEGER:
            return int(self.value)
        return self.value

class GroupRate(models.Model):
    MEN = 'men'
    WOMEN = 'women'
    YOUTH = 'youth'
    CHILDREN = 'children'

    GROUP_CHOICES = [
        (MEN, 'Men'),
        (WOMEN, 'Women'),
        (YOUTH, 'Youth'),
        (CHILDREN, 'Children'),
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
    ADMIN = 'admin'
    PRIEST = 'priest'
    SECRETARY = 'secretary'

    ROLE_CHOICES = [
        (ADMIN, 'Admin'),
        (PRIEST, 'Priest'),
        (SECRETARY, 'Secretary/Recorder'),
    ]
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=SECRETARY)
    phone = models.CharField(max_length=20, blank=True)
    
    class Meta:
        db_table = 'users'
    
    def is_priest(self):
        return self.role == PRIEST
    
    def is_admin(self):
        return self.role == ADMIN
    
    def is_secretary(self):
        return self.role == SECRETARY

