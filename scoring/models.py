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
        ('PRO', 'Compte Pro / Business'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comptes')
    type_compte = models.CharField(max_length=20, choices=TYPE_CHOICES, default='COURANT')
    solde = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    numero_compte = models.CharField(max_length=30, unique=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    est_actif = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.get_type_compte_display()} ({self.numero_compte})"

class Carte(models.Model):
    compte = models.ForeignKey(Compte, on_delete=models.CASCADE, related_name='cartes')
    numero_visible = models.CharField(max_length=4)
    date_expiration = models.DateField()
    plafond_paiement = models.IntegerField(default=2000)
    plafond_retrait = models.IntegerField(default=500)
    est_bloquee = models.BooleanField(default=False)
    sans_contact_actif = models.BooleanField(default=True)
    paiement_etranger_actif = models.BooleanField(default=False)
    
    def __str__(self):
        return f"Carte **** {self.numero_visible}"

# --- BÉNÉFICIAIRES ---
class Beneficiaire(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='beneficiaires')
    nom = models.CharField(max_length=100)
    iban = models.CharField(max_length=34)
    date_ajout = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nom} - {self.iban}"

# --- TRANSACTIONS ---
class Transaction(models.Model):
    TYPE_CHOICES = [('DEBIT', 'Débit'), ('CREDIT', 'Crédit')]

    CATEGORIE_CHOICES = [
        ('ALIM', 'Alimentation & Courses'),
        ('LOGEMENT', 'Logement & Factures'),
        ('TRANSPORT', 'Transport'),
        ('LOISIRS', 'Loisirs & Sorties'),
        ('SANTE', 'Santé'),
        ('SHOPPING', 'Shopping'),
        ('VIREMENT', 'Virement'),
        ('SALAIRE', 'Salaire & Revenus'),
        ('AUTRE', 'Autre'),
    ]

    compte = models.ForeignKey(Compte, on_delete=models.CASCADE, related_name='transactions')
    montant = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    libelle = models.CharField(max_length=100, blank=True)
    date_execution = models.DateTimeField(default=timezone.now)
    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES, default='AUTRE')

# --- SIMULATION & CRÉDIT ---
class ProduitPret(models.Model):
    nom = models.CharField(max_length=100)
    taux_ref = models.DecimalField(max_digits=5, decimal_places=2, default=3.50)
    
    def __str__(self):
        return self.nom

class TypeEmploi(models.Model):
    nom = models.CharField(max_length=50)

    def __str__(self):
        return self.nom

class TypeLogement(models.Model):
    nom = models.CharField(max_length=50)

    def __str__(self):
        return self.nom

class DemandeCredit(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En Attente'),
        ('ACCEPTEE', 'Acceptée'),
        ('REFUSEE', 'Refusée'),
    ]
    ETAT_SANTE_CHOIX = [('BON', 'Bon'), ('MOYEN', 'Moyen'), ('FAIBLE', 'Faible')]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    produit = models.ForeignKey(ProduitPret, on_delete=models.SET_NULL, null=True, blank=True)
    montant_souhaite = models.IntegerField(default=0)
    duree_souhaitee_annees = models.IntegerField(default=0)
    apport_personnel = models.IntegerField(default=0)
    revenus_mensuels = models.IntegerField(default=0)
    loyer_actuel = models.IntegerField(default=0)
    dettes_mensuelles = models.IntegerField(default=0)
    enfants_a_charge = models.IntegerField(default=0)
    emploi_snapshot = models.ForeignKey(TypeEmploi, on_delete=models.SET_NULL, null=True, blank=True)
    logement_snapshot = models.ForeignKey(TypeLogement, on_delete=models.SET_NULL, null=True, blank=True)
    sante_snapshot = models.CharField(max_length=10, choices=ETAT_SANTE_CHOIX, default='BON')
    score_calcule = models.IntegerField(null=True, blank=True)
    taux_calcule = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    recommendation = models.CharField(max_length=50, blank=True)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    date_demande = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.produit.nom if self.produit else 'Produit inconnu'} ({self.statut})"