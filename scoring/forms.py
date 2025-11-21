from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import DemandeCredit, TypeEmploi, TypeLogement, ProduitPret, Compte, Transaction, Beneficiaire

# --- UTILITAIRE DE VALIDATION IBAN (Version Souple pour Simulation) ---
def valider_format_iban(iban_value):
    """
    Vérifie la structure de l'IBAN sans imposer la clé de contrôle bancaire réelle (Modulo 97).
    Permet d'utiliser des IBANs de test ou internationaux variés.
    """
    if not iban_value:
        return None
        
    # 1. Nettoyage (retirer espaces et tirets, mettre en majuscules)
    iban = iban_value.replace(" ", "").replace("-", "").upper()
    
    # 2. Vérifications de structure de base
    # Longueur min: 8 (ex: NO) max: 34
    if len(iban) < 8 or len(iban) > 34:
         raise ValidationError("La longueur de l'IBAN est incorrecte (entre 8 et 34 caractères).")

    # Doit commencer par 2 lettres (Code Pays)
    if not iban[:2].isalpha():
        raise ValidationError("L'IBAN doit commencer par le code pays (2 lettres).")

    # Le reste doit être alphanumérique (certains pays ont des lettres, mais pour votre cas souvent des chiffres)
    if not iban.isalnum():
        raise ValidationError("L'IBAN contient des caractères invalides.")

    return iban

# --- AUTHENTIFICATION ---

class InscriptionForm(forms.ModelForm):
    birth_date = forms.DateField(label="Date de naissance", widget=forms.DateInput(attrs={'type': 'date'}))
    birth_city = forms.CharField(label="Ville de naissance", max_length=100)
    password = forms.CharField(widget=forms.PasswordInput, label="Mot de passe")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirmer mot de passe")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            self.add_error('confirm_password', "Les mots de passe ne correspondent pas.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user

# --- BANQUE AU QUOTIDIEN & BENEFICIAIRES ---

class BeneficiaireForm(forms.ModelForm):
    class Meta:
        model = Beneficiaire
        fields = ['nom', 'iban']
        labels = {
            'nom': 'Nom du bénéficiaire',
            'iban': 'IBAN'
        }
    
    def clean_iban(self):
        iban = self.cleaned_data.get('iban')
        return valider_format_iban(iban)

class VirementForm(forms.Form):
    compte_emetteur = forms.ModelChoiceField(queryset=None, label="Compte à débiter")
    
    # Sélectionner un bénéficiaire existant
    beneficiaire_enregistre = forms.ModelChoiceField(
        queryset=None, 
        required=False, 
        label="Bénéficiaire enregistré",
        empty_label="-- Sélectionner un bénéficiaire --"
    )
    
    # Ou saisir un nouvel IBAN (Champ texte simple côté Python, géré par JS côté Template)
    nouveau_beneficiaire_iban = forms.CharField(
        required=False, 
        label="IBAN"
    )
    
    montant = forms.DecimalField(min_value=0.01, decimal_places=2, label="Montant (€)")
    motif = forms.CharField(max_length=100, required=False, label="Motif (facultatif)")

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['compte_emetteur'].queryset = Compte.objects.filter(user=user, est_actif=True)
        self.fields['beneficiaire_enregistre'].queryset = Beneficiaire.objects.filter(user=user)

    def clean_nouveau_beneficiaire_iban(self):
        iban = self.cleaned_data.get('nouveau_beneficiaire_iban')
        if iban:
            # On utilise la validation souple définie plus haut
            return valider_format_iban(iban)
        return iban

    def clean(self):
        cleaned_data = super().clean()
        bene = cleaned_data.get("beneficiaire_enregistre")
        iban = cleaned_data.get("nouveau_beneficiaire_iban")

        if not bene and not iban:
            raise forms.ValidationError("Veuillez sélectionner un bénéficiaire OU saisir un IBAN.")
            
        if bene and iban:
             # Priorité au bénéficiaire enregistré si les deux sont remplis
             cleaned_data['nouveau_beneficiaire_iban'] = None
             
        return cleaned_data

class OuvrirCompteForm(forms.Form):
    type_compte = forms.ChoiceField(choices=[], label="Type de compte")

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        comptes_existants = Compte.objects.filter(user=user, est_actif=True).values_list('type_compte', flat=True)
        choix_possibles = [c for c in Compte.TYPE_CHOICES if c[0] not in comptes_existants]
        self.fields['type_compte'].choices = choix_possibles

class CloturerCompteForm(forms.Form):
    compte_destination = forms.ModelChoiceField(queryset=None, label="Virer le solde restant vers", required=False)
    password = forms.CharField(widget=forms.PasswordInput, label="Confirmez avec votre mot de passe")

    def __init__(self, user, compte_a_fermer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['compte_destination'].queryset = Compte.objects.filter(user=user, est_actif=True).exclude(id=compte_a_fermer.id)

# --- FILTRES & STATS ---

class TransactionFilterForm(forms.Form):
    date_debut = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_fin = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    type_transaction = forms.ChoiceField(choices=[('', 'Tous')] + Transaction.TYPE_CHOICES, required=False)
    categorie = forms.ChoiceField(choices=[('', 'Toutes')] + Transaction.CATEGORIE_CHOICES, required=False)
    montant_min = forms.DecimalField(required=False, min_value=0)
    montant_max = forms.DecimalField(required=False, min_value=0)

# --- CRÉDIT & SIMULATION ---

class SimulationPretForm(forms.ModelForm):
    revenus_mensuels = forms.IntegerField(label="Vos revenus mensuels nets (€)")
    loyer_actuel = forms.IntegerField(label="Loyer actuel / Charges (€)", required=False)
    dettes_mensuelles = forms.IntegerField(label="Autres crédits en cours (€)", required=False)
    
    class Meta:
        model = DemandeCredit
        exclude = [
            'user', 'statut', 'date_demande',
            'score_calcule', 'taux_calcule', 'recommendation',
            'sante_snapshot', 'ia_decision', 'mensualite_calculee'
        ]
