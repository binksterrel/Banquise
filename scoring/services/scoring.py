from decimal import Decimal
from math import ceil
from datetime import date
from django.utils import timezone
from ..ml import predict_credit, is_model_available
from ..models import DemandeCredit

def months_diff(d1, d2):
    return (d1.year - d2.year) * 12 + (d1.month - d2.month)

def add_months(d, n):
    year = d.year + (d.month - 1 + n) // 12
    month = (d.month - 1 + n) % 12 + 1
    day = min(d.day, [31,
                      29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                      31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)

def calculate_mensualite(montant, duree_mois, taux_annuel):
    montant = Decimal(montant)
    taux_mensuel = (Decimal(taux_annuel) / Decimal("100")) / Decimal("12")
    nb_mois = int(duree_mois)
    if taux_mensuel > 0:
        val = montant * taux_mensuel / (1 - (1 + taux_mensuel) ** (-nb_mois))
    else:
        val = montant / nb_mois
    return val

def next_installment_date(credit: DemandeCredit):
    total_months = max(1, (credit.duree_souhaitee_annees or 1) * 12)
    already_paid = credit.echeances_payees or 0
    if already_paid >= total_months:
        return None
    base_date = credit.date_acceptation or credit.date_demande.date()
    jour = min(max(1, credit.jour_prelevement or 1), 28)
    next_month = add_months(base_date.replace(day=1), 1)
    start = date(next_month.year, next_month.month, jour)
    return add_months(start, already_paid)

def build_credit_schedule(credit: DemandeCredit):
    total_months = max(1, (credit.duree_souhaitee_annees or 1) * 12)
    base_date = credit.date_acceptation or credit.date_demande.date()
    jour = min(max(1, credit.jour_prelevement or 1), 28)
    next_month = add_months(base_date.replace(day=1), 1)
    start = date(next_month.year, next_month.month, jour)
    schedule = []
    for i in range(total_months):
        due_date = add_months(start, i)
        schedule.append({
            'numero': i + 1,
            'date': due_date,
            'montant': credit.mensualite_calculee or Decimal("0"),
            'status': 'PAYEE' if (credit.echeances_payees or 0) > i else 'A_VENIR'
        })
    return schedule

def evaluate_credit_demand(demande: DemandeCredit):
    """
    Evaluates credit request using Hard Rules and ML Model.
    Update demande fields (mensualite, score_calcule, ia_decision, recommendation) but does NOT save.
    Returns calculated values as dict for immediate use.
    """
    base_rate = demande.produit.taux_ref if demande.produit else Decimal("3.50")
    nb_mois = max(1, (demande.duree_souhaitee_annees or 0) * 12)
    
    mensualite = calculate_mensualite(demande.montant_souhaite, nb_mois, base_rate)
    
    # Safety Check
    min_payment = Decimal(demande.montant_souhaite) / Decimal(nb_mois)
    if mensualite < min_payment:
        mensualite = min_payment

    demande.mensualite_calculee = mensualite

    dettes = Decimal(demande.dettes_mensuelles or 0) + Decimal(demande.loyer_actuel or 0)
    revs = Decimal(demande.revenus_mensuels or 1)
    dti = ((mensualite + dettes) / revs) * Decimal("100")

    knockout_reason = None
    if mensualite < min_payment:
         knockout_reason = "Mensualité insuffisante pour couvrir le capital."
    
    if dti > Decimal("45"):
        knockout_reason = f"Taux d'endettement excessif ({dti:.1f}% > 45%)."

    deps = int(demande.enfants_a_charge or 0)
    subsistence = Decimal("800") + (Decimal("300") * deps)
    reste = revs - (dettes + mensualite)
    if reste < subsistence:
         knockout_reason = f"Reste à vivre insuffisant ({reste:.0f}€ < {subsistence}€)."

    final_score = 0
    decision = 'REFUSEE'
    recommendation = ""

    if knockout_reason:
        final_score = 0
        decision = 'REFUSEE'
        recommendation = f"Refus automatique : {knockout_reason}"
    else:
        ml_result = None
        if is_model_available():
            try:
                payload = {
                    "revenus_mensuels": float(revs),
                    "montant_souhaite": float(demande.montant_souhaite),
                    "duree_mois": nb_mois,
                    "historique_credit": 1,
                    "personnes_a_charge": deps,
                    "marie": 1 if demande.marie else 0,
                    "diplome": 1 if demande.diplome else 0,
                    "independant": 0,
                }
                ml_result = predict_credit(payload)
            except: pass
        
        if ml_result:
            base_score = ml_result["score_0_100"]
            policy_adj = 0
            if demande.sante_snapshot == 'BON': policy_adj += 5
            if demande.apport_personnel >= demande.montant_souhaite * Decimal("0.1"): policy_adj += 10
            final_score = min(100, max(0, base_score + policy_adj))
            decision = 'ACCEPTEE' if final_score >= 50 else 'REFUSEE'
            recommendation = f"Score mis à jour : {final_score}/100"
        else:
            final_score = 50
            decision = 'EN_ATTENTE'
            recommendation = "En attente révision"

    demande.score_calcule = final_score
    demande.ia_decision = decision
    demande.recommendation = recommendation
    
    return {
        'mensualite': mensualite,
        'dti': dti,
        'reste_vivre': reste,
        'score': final_score,
        'decision': decision,
        'recommendation': recommendation,
        'knockout_reason': knockout_reason,
        'taux_mensuel': (Decimal(base_rate) / Decimal("100")) / Decimal("12"),
        'taux_calcule': base_rate,
        'nb_mois': nb_mois
    }
