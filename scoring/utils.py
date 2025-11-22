from decimal import Decimal
from datetime import timedelta

from django.db import models
from django.utils import timezone

from .models import ProfilClient, DemandeDecouvert


def _base_overdraft_limit(user):
    profil, _ = ProfilClient.objects.get_or_create(user=user, defaults={
        'abonnement': 'ESSENTIEL',
        'prochaine_facturation': timezone.now().date() + timedelta(days=30)
    })
    return {
        'ESSENTIEL': Decimal("100.00"),
        'PLUS': Decimal("500.00"),
        'INFINITE': Decimal("1000.00")
    }.get(profil.abonnement, Decimal("100.00"))


def _active_decouvert_boost(user):
    return DemandeDecouvert.objects.filter(
        user=user,
        statut='ACCEPTEE'
    ).filter(
        models.Q(expire_le__isnull=True) | models.Q(expire_le__gte=timezone.now().date())
    ).order_by('-cree_le').first()


def overdraft_limit_for_user(user):
    base = _base_overdraft_limit(user)
    boost = _active_decouvert_boost(user)
    return max(base, boost.montant_souhaite) if boost else base
