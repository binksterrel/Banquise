import os
import django

# 1. Configuration de l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Banquise.settings')
django.setup()

from django.contrib.auth.models import User
from scoring.models import Beneficiaire

def run():
    print("🔧 Démarrage de la correction des noms en base de données...\n")

    # --- 1. CORRECTION DES UTILISATEURS ---
    users = User.objects.all()
    count_users = 0
    
    print(f"Traitement de {users.count()} utilisateurs...")
    
    for user in users:
        # Vérifie si le nom n'est pas déjà en majuscules pour éviter des écritures inutiles
        if user.last_name and not user.last_name.isupper():
            old_name = user.last_name
            user.last_name = user.last_name.upper()
            user.save()
            print(f"  - User : {old_name} -> {user.last_name}")
            count_users += 1
    
    print(f"✅ {count_users} noms d'utilisateurs corrigés.\n")

    # --- 2. CORRECTION DES BÉNÉFICIAIRES ---
    beneficiaires = Beneficiaire.objects.all()
    count_bene = 0
    
    print(f"Traitement de {beneficiaires.count()} bénéficiaires...")
    
    for bene in beneficiaires:
        # On met tout le champ 'nom' du bénéficiaire en majuscules
        if bene.nom and not bene.nom.isupper():
            old_nom = bene.nom
            bene.nom = bene.nom.upper()
            bene.save()
            print(f"  - Bénéficiaire : {old_nom} -> {bene.nom}")
            count_bene += 1

    print(f"✅ {count_bene} bénéficiaires corrigés.\n")
    print("🎉 Terminé ! Tous les noms sont maintenant en majuscules.")

if __name__ == '__main__':
    run()