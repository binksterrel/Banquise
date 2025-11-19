from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# --- UTILISATEURS ---
class ProfilClient(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil')
    date_de_naissance = models.DateField(null=True, blank=True)
    ville_naissance = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=15, blank=True)

    def __str__(self):
        return self.user.username

# --- BANQUE AU QUOTIDIEN ---
class Compte(models.Model):
    TYPE_CHOICES = [
        ('COURANT', 'Compte Courant'),
        ('EPARGNE', 'Compte Épargne'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comptes')
    type_compte = models.CharField(max_length=20, choices=TYPE_CHOICES, default='COURANT')
    solde = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    numero_compte = models.CharField(max_length=30, unique=True) # Ex: FR76...
    date_creation = models.DateTimeField(auto_now_add=True)
    est_actif = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.get_type_compte_display()} ({self.numero_compte})"

class Carte(models.Model):
    compte = models.ForeignKey(Compte, on_delete=models.CASCADE, related_name='cartes')
    numero_visible = models.CharField(max_length=4) # Les 4 derniers chiffres
    date_expiration = models.DateField()
    plafond_paiement = models.IntegerField(default=2000)
    plafond_retrait = models.IntegerField(default=500)
    est_bloquee = models.BooleanField(default=False)

    # Champs pour les fonctionnalités Switch
    sans_contact_actif = models.BooleanField(default=True)
    paiement_etranger_actif = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Carte **** {self.numero_visible}"

class Transaction(models.Model):
    TYPE_CHOICES = [('DEBIT', 'Débit'), ('CREDIT', 'Crédit')]
    compte = models.ForeignKey(Compte, on_delete=models.CASCADE, related_name='transactions')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    libelle = models.CharField(max_length=100)
    date_execution = models.DateTimeField(default=timezone.now)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)

# --- SIMULATION & CRÉDIT ---
class ProduitPret(models.Model):
    nom = models.CharField(max_length=100) # Ex: Prêt Immo, Prêt Conso
    taux_ref = models.DecimalField(max_digits=5, decimal_places=2, default=3.50)
    
    def __str__(self): return self.nom

class TypeEmploi(models.Model):
    nom = models.CharField(max_length=50)
    def __str__(self): return self.nom

class TypeLogement(models.Model):
    nom = models.CharField(max_length=50)
    def __str__(self): return self.nom

class DemandeCredit(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En Attente'),
        ('ACCEPTEE', 'Acceptée'),
        ('REFUSEE', 'Refusée'),
    ]
    ETAT_SANTE_CHOIX = [('BON', 'Bon'), ('MOYEN', 'Moyen'), ('FAIBLE', 'Faible')]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    produit = models.ForeignKey(ProduitPret, on_delete=models.SET_NULL, null=True)
    
    # Données financières
    montant_souhaite = models.IntegerField()
    duree_souhaitee_annees = models.IntegerField()
    apport_personnel = models.IntegerField(default=0)
    revenus_mensuels = models.IntegerField()
    loyer_actuel = models.IntegerField(default=0)
    dettes_mensuelles = models.IntegerField(default=0)
    enfants_a_charge = models.IntegerField(default=0)
    
    # Profiling
    emploi_snapshot = models.ForeignKey(TypeEmploi, on_delete=models.SET_NULL, null=True)
    logement_snapshot = models.ForeignKey(TypeLogement, on_delete=models.SET_NULL, null=True)
    sante_snapshot = models.CharField(max_length=10, choices=ETAT_SANTE_CHOIX, default='BON')

    # Résultats calculés (IA Mock)
    score_calcule = models.IntegerField(null=True, blank=True) # 0 à 100
    taux_calcule = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    recommendation = models.CharField(max_length=50, blank=True) # Excellent, Moyen, Risqué
    
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    date_demande = models.DateTimeField(auto_now_add=True)