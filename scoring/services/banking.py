import re
import uuid
from decimal import Decimal
from datetime import timedelta
from django.db import transaction, models
from django.utils import timezone
from django.urls import reverse
from ..models import Compte, Carte, Transaction, ProfilClient, VirementProgramme, Beneficiaire, Notification
from ..utils import overdraft_limit_for_user
from .notifications import notifier

def normalize_iban(value: str) -> str:
    return re.sub(r"[\s-]+", "", (value or "")).upper()

def find_account_by_iban(iban_norm: str):
    """Recherche insensible aux espaces/majuscules."""
    return Compte.objects.filter(numero_compte__iexact=iban_norm).first()

def normalize_phone(value: str) -> str:
    return re.sub(r"[^0-9]", "", value or "")

def find_account_by_phone(phone_norm: str):
    profil = ProfilClient.objects.filter(telephone=phone_norm).select_related('user').first()
    if not profil:
        for p in ProfilClient.objects.exclude(telephone='').select_related('user'):
            if normalize_phone(p.telephone) == phone_norm:
                profil = p
                break
    if not profil:
        return None
    return Compte.objects.filter(user=profil.user, est_actif=True).order_by('id').first()

def enforce_overdraft(compte):
    """Blocage/déblocage des cartes en fonction du découvert autorisé."""
    limit = overdraft_limit_for_user(compte.user)
    solsous = compte.solde
    cartes = Carte.objects.filter(compte=compte)

    # Alerte préventive quand on approche du seuil de blocage
    seuil_alerte = -limit * Decimal("0.8")
    if solsous <= seuil_alerte:
        recent_alert = Notification.objects.filter(
            user=compte.user,
            titre__icontains="Alerte découvert",
            date_creation__gte=timezone.now() - timedelta(hours=12)
        ).exists()
        if not recent_alert:
            notifier(
                compte.user,
                "Alerte découvert",
                f"Votre solde ({solsous} €) s'approche de la limite autorisée ({-limit} €).",
                "INFO",
                url=reverse('dashboard')
            )

    if solsous < -limit:
        # Blocage si pas déjà bloqué
        updated = cartes.filter(est_bloquee=False).update(est_bloquee=True)
        if updated:
            notifier(compte.user, "Découvert dépassé", "Vos cartes sont bloquées jusqu'au retour en dessous du découvert autorisé.", "TRANSACTION", url=reverse('cartes'))
    else:
        # Déblocage si le compte est revenu au-dessus du découvert autorisé
        updated = cartes.filter(est_bloquee=True).update(est_bloquee=False)
        if updated:
            notifier(compte.user, "Cartes débloquées", "Votre solde est revenu au-dessus du découvert autorisé.", "TRANSACTION", url=reverse('cartes'))

def execute_virement(compte, montant, motif, target_iban, target_phone, beneficiaire, request_user, operation_id):
    target_iban = target_iban or ''
    target_phone = target_phone or ''
    destinataire_str = ""
    if beneficiaire:
        info_parts = [beneficiaire.nom]
        if target_phone:
            info_parts.append(f"tel {target_phone}")
        if target_iban:
            info_parts.append(f"IBAN {target_iban}")
        destinataire_str = " - ".join(info_parts)
    elif target_iban:
        destinataire_str = f"IBAN {target_iban}"
    elif target_phone:
        destinataire_str = f"Téléphone {target_phone}"

    compte_destinataire = None
    if target_iban:
        compte_destinataire = find_account_by_iban(normalize_iban(target_iban))
    if not compte_destinataire and target_phone:
        compte_destinataire = find_account_by_phone(target_phone)

    if target_phone and not compte_destinataire:
        raise ValueError("Aucun compte Banquise trouvé pour ce numéro.")

    # Deadlock prevention: Lock accounts in deterministic order (by ID)
    ids_to_lock = sorted([id for id in [compte.id, getattr(compte_destinataire, 'id', None)] if id is not None])
    
    with transaction.atomic():
        # Lock all involved accounts in order
        locked_accounts = {
            c.id: c for c in Compte.objects.select_for_update().filter(id__in=ids_to_lock, est_actif=True)
        }
        
        # Verify emitter ownership/validity after lock
        if compte.id not in locked_accounts:
             # Should not happen if passed object corresponds to DB row, unless deleted/inactive
             raise ValueError("Compte émetteur introuvable ou inactif.")
        
        emetteur = locked_accounts[compte.id]
        if emetteur.user != request_user:
             raise ValueError("Accès refusé au compte émetteur.")

        destinataire_locked = None
        if compte_destinataire:
            destinataire_locked = locked_accounts.get(compte_destinataire.id)
            # If internal destination not found/active after lock (unlikely but possible)
            if not destinataire_locked:
                 # Soft fail or treat as external? For Banquise internal: strict fail better
                 pass 

        if Transaction.objects.filter(operation_id=operation_id, compte=emetteur, type='DEBIT').exists():
            return "duplicate"

        if emetteur.solde < montant:
            raise ValueError("Solde insuffisant pour effectuer ce virement.")

        emetteur.solde -= montant
        emetteur.save(update_fields=['solde'])
        Transaction.objects.create(
            compte=emetteur,
            montant=-montant,
            libelle=f"Virement vers {destinataire_str} - {motif}",
            type='DEBIT',
            categorie='VIREMENT',
            operation_id=operation_id
        )
        notifier(request_user, "Virement envoyé", f"Virement vers {destinataire_str} de {montant} €", "VIREMENT", url=reverse('dashboard'))
        enforce_overdraft(emetteur)

        if destinataire_locked:
            destinataire_locked.solde += montant
            destinataire_locked.save(update_fields=['solde'])
            Transaction.objects.create(
                compte=destinataire_locked,
                montant=montant,
                libelle=f"Virement reçu de {request_user.first_name} {request_user.last_name} - {motif}",
                type='CREDIT',
                categorie='VIREMENT',
                operation_id=operation_id
            )
            notifier(destinataire_locked.user, "Virement reçu", f"Vous avez reçu {montant} € de {request_user.get_full_name()}", "VIREMENT", url=reverse('dashboard'))
            enforce_overdraft(destinataire_locked)
    return "ok"
