import os
import django
import random
from datetime import timedelta
from django.utils import timezone

# 1. Configuration de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Banquise.settings')
django.setup()

from scoring.models import Compte, Transaction, Beneficiaire

# --- DONNÉES DE TEST ---
CATEGORIES = ['ALIM', 'LOGEMENT', 'TRANSPORT', 'LOISIRS', 'SANTE', 'SHOPPING', 'AUTRE']
ENSEIGNES = {
    'ALIM': ["Carrefour", "Leclerc", "Auchan", "Boulangerie Paul", "Monoprix", "Picard", "Franprix"],
    'LOGEMENT': ["EDF", "Engie", "Loyer", "Castorama", "IKEA", "Leroy Merlin"],
    'TRANSPORT': ["SNCF", "Uber", "Total Access", "Shell", "RATP", "Bolt", "Lime"],
    'LOISIRS': ["Netflix", "Cinéma Pathé", "Spotify", "Fnac", "Basic Fit", "Bar Le QG", "Playstation Store"],
    'SANTE': ["Pharmacie Centrale", "Doctolib", "Laboratoire", "Optic 2000"],
    'SHOPPING': ["Amazon", "Zara", "H&M", "Sephora", "Zalando", "Apple Store", "Nike"],
    'AUTRE': ["Tabac", "La Poste", "Fleuriste", "Pressing"]
}

def create_transaction(compte, type_tx, categorie, montant, libelle, date_delta_days=0):
    """Crée une transaction avec une date dans le passé"""
    date_exec = timezone.now() - timedelta(days=date_delta_days)
    Transaction.objects.create(
        compte=compte,
        type=type_tx,
        categorie=categorie,
        montant=montant,
        libelle=libelle,
        date_execution=date_exec
    )

def run():
    print("🚀 Ajout de nouvelles transactions aux comptes existants...\n")

    # Récupérer tous les comptes actifs
    all_accounts = list(Compte.objects.filter(est_actif=True))
    
    if not all_accounts:
        print("❌ Aucun compte actif trouvé. Lancez d'abord 'populate_banquise.py'.")
        return

    print(f"ℹ️  Comptes trouvés : {len(all_accounts)}")

    # 1. GÉNÉRATION DE DÉPENSES SUPPLÉMENTAIRES
    print("💸 Simulation de la vie quotidienne (Dépenses)...")
    count_depenses = 0
    
    for compte in all_accounts:
        # Entre 3 et 8 nouvelles dépenses par compte
        nb_tx = random.randint(3, 8)
        for _ in range(nb_tx):
            cat = random.choice(CATEGORIES)
            enseigne = random.choice(ENSEIGNES.get(cat, ["Commerce"]))
            montant = float(random.randint(5, 120)) + random.choice([0.50, 0.90, 0.99, 0.00])
            
            # On débite
            compte.solde = float(compte.solde) - montant
            
            # Date aléatoire dans les 10 derniers jours
            jours_passes = random.randint(0, 10)
            
            create_transaction(compte, 'DEBIT', cat, montant, enseigne, jours_passes)
            count_depenses += 1
        
        compte.save()

    # 2. GÉNÉRATION DE NOUVEAUX VIREMENTS
    print("🔄 Simulation de mouvements d'argent (Virements)...")
    count_virements = 0
    
    for _ in range(15): # 15 nouveaux virements
        sender = random.choice(all_accounts)
        receiver = random.choice(all_accounts)

        # Pas de virement vers soi-même pour cet exercice
        if sender.user != receiver.user:
            montant_virement = float(random.randint(15, 300))
            
            # Vérif solde (on autorise un petit découvert pour le test)
            if float(sender.solde) >= (montant_virement - 100):
                # Débit envoyeur
                sender.solde = float(sender.solde) - montant_virement
                sender.save()
                create_transaction(
                    sender, 
                    'DEBIT', 
                    'VIREMENT', 
                    montant_virement, 
                    f"Virement vers {receiver.user.last_name} {receiver.user.first_name}", 
                    random.randint(0, 5)
                )

                # Crédit receveur
                receiver.solde = float(receiver.solde) + montant_virement
                receiver.save()
                create_transaction(
                    receiver, 
                    'CREDIT', 
                    'VIREMENT', 
                    montant_virement, 
                    f"Virement reçu de {sender.user.last_name} {sender.user.first_name}", 
                    random.randint(0, 5)
                )
                
                # Ajouter aux bénéficiaires si pas déjà fait
                Beneficiaire.objects.get_or_create(
                    user=sender.user,
                    iban=receiver.numero_compte,
                    defaults={'nom': f"{receiver.user.first_name} {receiver.user.last_name}"}
                )
                count_virements += 1

    print("\n✨ Terminé !")
    print(f"   - {count_depenses} nouvelles dépenses ajoutées.")
    print(f"   - {count_virements} nouveaux virements effectués.")
    print("   - Les soldes ont été mis à jour.")

if __name__ == '__main__':
    run()