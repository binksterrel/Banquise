import os
import random
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Banquise.settings")
django.setup()

from django.contrib.auth.models import User
from django.utils import timezone

from scoring.models import DemandeCredit, ProduitPret, TypeEmploi, TypeLogement


def prepare_reference_data():
    ProduitPret.objects.get_or_create(nom="Prêt personnel 180k", taux_ref=3.5)
    ProduitPret.objects.get_or_create(nom="Prêt immobilier 360k", taux_ref=2.9)
    TypeEmploi.objects.get_or_create(nom="CDI")
    TypeEmploi.objects.get_or_create(nom="CDD")
    TypeEmploi.objects.get_or_create(nom="Indépendant")
    TypeLogement.objects.get_or_create(nom="Appartement")
    TypeLogement.objects.get_or_create(nom="Maison")


def compute_score(decision_data):
    mensualite = decision_data["mensualite"]
    revenus = decision_data["revenus_mensuels"] or Decimal("1")
    dettes = decision_data["dettes_mensuelles"] + decision_data["loyer_actuel"]
    dti = ((mensualite + dettes) / revenus) * Decimal("100")
    montant = decision_data["montant_souhaite"]
    apport = decision_data["apport_personnel"]
    ltv = Decimal("100") * (Decimal("1") - (apport / montant))
    score = Decimal("100")
    if dti > Decimal("30"):
        score -= (dti - Decimal("30")) * Decimal("1.5")
    if ltv > Decimal("80"):
        score -= (ltv - Decimal("80")) * Decimal("0.5")
    if revenus < Decimal("2000"):
        score -= Decimal("10")
    if apport >= montant * Decimal("0.2"):
        score += Decimal("8")
    if decision_data["emploi_snapshot"] and decision_data["emploi_snapshot"].nom.lower().startswith("cdi"):
        score += Decimal("5")
    if decision_data["sante_snapshot"] == "BON":
        score += Decimal("2")
    score = int(max(0, min(100, score)))
    return float(dti), float(ltv), score


def decide(score, dti, ltv, montant, apport, revenus):
    dti_limit = 40
    if revenus >= 6000:
        dti_limit = 45
    ltv_limit = 90
    if montant >= Decimal("100000") and apport >= montant * Decimal("0.1"):
        ltv_limit = 95
    if montant >= Decimal("250000") and apport >= montant * Decimal("0.15"):
        ltv_limit = 97
    ia_decision = "ACCEPTEE" if (dti <= dti_limit and ltv <= ltv_limit and score >= 60) else "REFUSEE"
    return ia_decision, dti_limit, ltv_limit


def create_request(user, product, emploi, logement, montant):
    revenus = random.randint(2500, 9000)
    montant = Decimal(montant)
    mensualite = montant / Decimal(random.choice([120, 180, 240]))
    decision_data = {
        "mensualite": mensualite,
        "dettes_mensuelles": Decimal(random.randint(100, 900)),
        "loyer_actuel": Decimal(random.randint(400, 1800)),
        "revenus_mensuels": Decimal(revenus),
        "apport_personnel": Decimal(random.randint(5000, max(5000, int(montant * Decimal("0.3"))))),
        "montant_souhaite": montant,
        "emploi_snapshot": emploi,
        "sante_snapshot": random.choice(["BON", "MOYEN", "FAIBLE"]),
    }
    dti, ltv, score = compute_score(decision_data)
    ia_decision, dti_limit, ltv_limit = decide(score, dti, ltv, montant, decision_data["apport_personnel"], revenus)
    demande = DemandeCredit(
        user=user,
        produit=product,
        montant_souhaite=montant,
        duree_souhaitee_annees=random.choice([10, 15, 20]),
        apport_personnel=decision_data["apport_personnel"],
        revenus_mensuels=revenus,
        loyer_actuel=decision_data["loyer_actuel"],
        dettes_mensuelles=decision_data["dettes_mensuelles"],
        enfants_a_charge=random.randint(0, 3),
        emploi_snapshot=emploi,
        logement_snapshot=logement,
        sante_snapshot=decision_data["sante_snapshot"],
        score_calcule=score,
        ia_decision=ia_decision,
        recommendation=f"Avis IA {ia_decision} (score {score}, dti {dti:.1f}%, ltv {ltv:.1f}%, seuils {dti_limit}/{ltv_limit})",
        statut="EN_ATTENTE",
        date_demande=timezone.now(),
    )
    demande.save()
    print(f"{user.username}: {montant} € → {ia_decision} (score {score}, dti {dti:.1f}, ltv {ltv:.1f})")


def main():
    prepare_reference_data()
    produits = list(ProduitPret.objects.all())
    emplois = list(TypeEmploi.objects.all())
    logements = list(TypeLogement.objects.all())
    for i in range(1, 11):
        user, created = User.objects.get_or_create(username=f"ia_user_{i}", defaults={
            "first_name": f"IA{i}",
            "last_name": "Client",
            "email": f"ia{i}@example.com",
        })
        if created:
            user.set_password("ia1234")
            user.save()
        produit = random.choice(produits)
        emploi = random.choice(emplois)
        logement = random.choice(logements)
        montant = random.randint(5000, 250000) // 1000 * 1000
        create_request(user, produit, emploi, logement, montant)


if __name__ == "__main__":
    main()
