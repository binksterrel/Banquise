import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Banquise.settings")
django.setup()

from django.contrib.auth import get_user_model
from scoring.models import ProduitPret, TypeEmploi, TypeLogement, Compte
from scoring.forms import SimulationPretForm

User = get_user_model()
try:
    user = User.objects.get(username='tester')
except User.DoesNotExist:
    user = User.objects.create_user(username='tester', password='password')

produit, _ = ProduitPret.objects.get_or_create(nom="Conso", defaults={'taux_ref': 3.5})
cdi, _ = TypeEmploi.objects.get_or_create(nom="CDI")
logement, _ = TypeLogement.objects.get_or_create(nom="Propriétaire")
compte, _ = Compte.objects.get_or_create(user=user, type_compte='COURANT', defaults={'est_actif': True, 'solde': 100})

data = {
    'montant_souhaite': 120000,
    'duree_souhaitee_annees': 10,
    'revenus_mensuels': 5000,
    'dettes_mensuelles': 0,
    'produit': produit.id,
    'emploi_snapshot': cdi.id,
    'logement_snapshot': logement.id,
    'compte_versement': compte.id,
    'soumise': 'on',
    'jour_prelevement': 5, # Added default
    'apport_personnel': 0, 
    'loyer_actuel': 0,
    'enfants_a_charge': 0,
}

form = SimulationPretForm(data, user=user)
if not form.is_valid():
    print("ERRORS:", form.errors)
else:
    print("VALID!")
