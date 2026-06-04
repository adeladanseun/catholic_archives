from django.db.models.signals import pre_delete
from django.core.exceptions import PermissionDenied
from django.dispatch import receiver

from mass_intentions.models import MassIntention
from yearly_contributions.models import YearlyContribution


@receiver(pre_delete, sender=MassIntention)
def protect_approved_mass_intention(sender, instance, **kwargs):
    """Prevent deletion of approved mass intentions at the model level"""
    if instance.is_approved:
        raise PermissionDenied(
            "Cannot delete an approved Mass Intention. "
            "Please contact a priest or admin to revoke approval first."
        )


@receiver(pre_delete, sender=YearlyContribution)
def protect_approved_yearly_contribution(sender, instance, **kwargs):
    """Prevent deletion of approved yearly contributions at the model level"""
    if instance.is_approved:
        raise PermissionDenied(
            "Cannot delete an approved Yearly Contribution. "
            "Please contact a priest or admin to revoke approval first."
        )