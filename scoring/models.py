from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# --- UTILISATEURS ---
class ProfilClient(models.Model):
    ABONNEMENT_CHOICES = [
        ('ESSENTIEL', 'Essentiel'),
        ('PLUS', 'Plus'),
        ('INFINITE', 'Infinite'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profil')
    date_de_naissance = models.DateField(null=True, blank=True)
    ville_naissance = models.CharField(max_length=100, blank=True)
    telephone = models.CharField(max_length=15, blank=True)
    abonnement = models.CharField(max_length=15, choices=ABONNEMENT_CHOICES, default='ESSENTIEL')
    prochain_abonnement = models.CharField(max_length=15, choices=ABONNEMENT_CHOICES, null=True, blank=True)
    prochaine_facturation = models.DateField(default=timezone.now)

    def __str__(self):
        return self.user.username


# --- SUPPORT & CHAT ---
class MessageSupport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='messages_support')
    contenu = models.TextField()
    est_admin = models.BooleanField(default=False)
    date_envoi = models.DateTimeField(auto_now_add=True)
    est_lu = models.BooleanField(default=False)
    image = models.ImageField(upload_to='support/', null=True, blank=True)
    mis_a_jour_le = models.DateTimeField(auto_now=True)
    a_ete_modifie = models.BooleanField(default=False)

    class Meta:
        ordering = ['date_envoi']

    def __str__(self):
        return f"{'Admin' if self.est_admin else self.user.username}: {self.contenu[:40]}"

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
    surnom = models.CharField(max_length=100, blank=True)
    iban = models.CharField(max_length=34)
    date_ajout = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        label = self.surnom or self.nom
        return f"{label} - {self.iban}"

# --- TRANSACTIONS ---
class Transaction(models.Model):
    TYPE_CHOICES = [
        ('DEBIT', 'Débit'),
        ('CREDIT', 'Crédit')
    ]

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

    ETAT_SANTE_CHOIX = [
        ('BON', 'Bon'),
        ('MOYEN', 'Moyen'),
        ('FAIBLE', 'Faible'),
    ]

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
    ia_decision = models.CharField(max_length=20, choices=STATUT_CHOICES, null=True, blank=True)
    mensualite_calculee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    soumise = models.BooleanField(default=False)
    echeances_payees = models.IntegerField(default=0)
    dernier_prelevement = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} - {self.produit.nom if self.produit else 'Produit inconnu'} ({self.statut})"


class DemandeDecouvert(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('ACCEPTEE', 'Acceptée'),
        ('REFUSEE', 'Refusée'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='demandes_decouvert')
    montant_souhaite = models.DecimalField(max_digits=10, decimal_places=2)
    statut = models.CharField(max_length=15, choices=STATUT_CHOICES, default='EN_ATTENTE')
    expire_le = models.DateField(null=True, blank=True)
    commentaire_admin = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    mis_a_jour_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-cree_le']

    def __str__(self):
        return f"{self.user.username} - {self.montant_souhaite}€ ({self.get_statut_display()})"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('VIREMENT', 'Virement'),
        ('TRANSACTION', 'Transaction'),
        ('CREDIT', 'Crédit'),
        ('INFO', 'Info'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    titre = models.CharField(max_length=100)
    contenu = models.TextField()
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='INFO')
    url = models.CharField(max_length=250, blank=True)
    est_lu = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date_creation']

    def __str__(self):
        return f"{self.user.username} - {self.titre}"
