import os
import django
import random
from datetime import timedelta
from django.utils import timezone

# 1. Configuration de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Banquise.settings')
django.setup()

from django.contrib.auth.models import User
from scoring.models import Compte, Carte, Transaction, ProfilClient, Beneficiaire

# --- DONNÉES DE TEST ---
PRENOMS = ["Thomas", "Sarah", "Julien", "Emma", "Lucas", "Léa", "Maxime", "Chloé", "Nicolas", "Camille", "Alexandre", "Manon", "Pierre", "Julie", "Antoine", "Océane", "Florian", "Laura", "Kevin", "Marie"]
NOMS = ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy", "Moreau", "Simon", "Laurent", "Lefebvre", "Michel", "Garcia", "David", "Bertrand", "Roux", "Vincent", "Fournier"]
VILLES = ["Paris", "Lyon", "Marseille", "Bordeaux", "Lille", "Toulouse", "Nantes", "Strasbourg"]
CATEGORIES = ['ALIM', 'LOGEMENT', 'TRANSPORT', 'LOISIRS', 'SANTE', 'SHOPPING', 'AUTRE']
ENSEIGNES = {
    'ALIM': ["Carrefour", "Leclerc", "Auchan", "Boulangerie Paul", "Monoprix"],
    'LOGEMENT': ["EDF", "Engie", "Loyer", "Castorama", "IKEA"],
    'TRANSPORT': ["SNCF", "Uber", "Total Access", "Shell", "RATP"],
    'LOISIRS': ["Netflix", "Cinéma Pathé", "Spotify", "Fnac", "Basic Fit"],
    'SANTE': ["Pharmacie Centrale", "Doctolib", "Laboratoire"],
    'SHOPPING': ["Amazon", "Zara", "H&M", "Sephora", "Zalando"],
    'AUTRE': ["Tabac", "La Poste", "Fleuriste"]
}

PASSWORD_COMMUN = "password123"

def generate_iban():
    """Génère un IBAN interne formaté sans espaces pour la compatibilité"""
    return f"FR76{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}"

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
    print("🚀 Démarrage du peuplement de la base de données Banquise...")

    users_created = []
    all_accounts = []

    # 1. CRÉATION DES UTILISATEURS ET COMPTES
    for i in range(20):
        first_name = PRENOMS[i]
        last_name = NOMS[i]
        username = f"{first_name.lower()}.{last_name.lower()}{random.randint(1,99)}"
        
        # Éviter les doublons
        if User.objects.filter(username=username).exists():
            continue

        user = User.objects.create_user(
            username=username, 
            password=PASSWORD_COMMUN,
            first_name=first_name,
            last_name=last_name,
            email=f"{username}@example.com"
        )
        users_created.append(user)

        # Profil Client
        ProfilClient.objects.create(
            user=user,
            ville_naissance=random.choice(VILLES),
            telephone=f"06{random.randint(10000000, 99999999)}"
        )

        # Compte Courant (Obligatoire)
        compte_courant = Compte.objects.create(
            user=user,
            type_compte='COURANT',
            solde=float(random.randint(500, 3000)),
            numero_compte=generate_iban(),
            est_actif=True
        )
        Carte.objects.create(
            compte=compte_courant,
            numero_visible=str(random.randint(1000,9999)),
            date_expiration=timezone.now() + timedelta(days=365*random.randint(1,4)),
            est_bloquee=False
        )
        all_accounts.append(compte_courant)

        # Compte Épargne (Aléatoire)
        if random.random() > 0.4: # 60% de chance
            compte_epargne = Compte.objects.create(
                user=user,
                type_compte='EPARGNE',
                solde=float(random.randint(2000, 15000)),
                numero_compte=generate_iban(),
                est_actif=True
            )
            # Pas de carte pour l'épargne généralement, mais on peut en mettre une pour le test
            Carte.objects.create(
                compte=compte_epargne,
                numero_visible=str(random.randint(1000,9999)),
                date_expiration=timezone.now() + timedelta(days=365*5),
                est_bloquee=False
            )
            all_accounts.append(compte_epargne)

        # Compte PRO (Aléatoire)
        if random.random() > 0.8: # 20% de chance
            compte_pro = Compte.objects.create(
                user=user,
                type_compte='PRO',
                solde=float(random.randint(5000, 50000)),
                numero_compte=generate_iban(),
                est_actif=True
            )
            Carte.objects.create(
                compte=compte_pro,
                numero_visible=str(random.randint(1000,9999)),
                date_expiration=timezone.now() + timedelta(days=365*2),
                est_bloquee=False
            )
            all_accounts.append(compte_pro)

        print(f"✅ Utilisateur créé : {username}")

    # 2. GÉNÉRATION DES TRANSACTIONS (DÉPENSES)
    print("💸 Génération des dépenses...")
    for compte in all_accounts:
        # Salaire initial
        create_transaction(compte, 'CREDIT', 'SALAIRE', 2500.00, f"Virement Salaire {random.choice(['Google', 'Amazon', 'Banquise', 'Mairie', 'Hopital'])}", 30)
        
        # Dépenses aléatoires (entre 5 et 15 par compte)
        for _ in range(random.randint(5, 15)):
            cat = random.choice(CATEGORIES)
            enseigne = random.choice(ENSEIGNES.get(cat, ["Commerce"]))
            montant = float(random.randint(5, 150)) + random.choice([0.50, 0.90, 0.99])
            
            compte.solde = float(compte.solde) - montant
            create_transaction(compte, 'DEBIT', cat, montant, enseigne, random.randint(1, 28))
        
        compte.save()

    # 3. VIREMENTS ENTRE UTILISATEURS (INTERNES)
    print("🔄 Génération des virements entre utilisateurs...")
    for _ in range(30): # 30 virements au total
        sender_account = random.choice(all_accounts)
        receiver_account = random.choice(all_accounts)

        # On ne se vire pas à soi-même ici (même si possible techniquement entre comptes différents)
        if sender_account.user != receiver_account.user:
            montant_virement = float(random.randint(20, 500))
            
            if sender_account.solde >= montant_virement:
                # Débit envoyeur
                sender_account.solde = float(sender_account.solde) - montant_virement
                sender_account.save()
                create_transaction(
                    sender_account, 
                    'DEBIT', 
                    'VIREMENT', 
                    montant_virement, 
                    f"Virement vers {receiver_account.user.last_name} {receiver_account.user.first_name}", 
                    random.randint(1, 10)
                )

                # Crédit receveur
                receiver_account.solde = float(receiver_account.solde) + montant_virement
                receiver_account.save()
                create_transaction(
                    receiver_account, 
                    'CREDIT', 
                    'VIREMENT', 
                    montant_virement, 
                    f"Virement reçu de {sender_account.user.last_name} {sender_account.user.first_name}", 
                    random.randint(1, 10)
                )
                
                # Création optionnelle d'un bénéficiaire pour que ça apparaisse dans la liste
                if random.random() > 0.5:
                    Beneficiaire.objects.get_or_create(
                        user=sender_account.user,
                        iban=receiver_account.numero_compte,
                        defaults={'nom': f"{receiver_account.user.first_name} {receiver_account.user.last_name}"}
                    )

    print("\n✨ Terminé ! La base de données a été peuplée.")
    print(f"👉 Connectez-vous avec : {users_created[0].username} / {PASSWORD_COMMUN}")

if __name__ == '__main__':
    run()