from django import forms
from django.contrib.auth.models import User
from .models import DemandeCredit, TypeEmploi, TypeLogement, ProduitPret, Compte

# --- AUTHENTIFICATION ---

class InscriptionForm(forms.ModelForm):
    password = forms.CharField(label="Mot de passe", widget=forms.PasswordInput)
    birth_date = forms.DateField(label="Date de naissance", widget=forms.DateInput(attrs={'type': 'date'}))
    birth_city = forms.CharField(label="Ville de naissance", max_length=100)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'password']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user

# --- BANQUE AU QUOTIDIEN ---

class VirementForm(forms.Form):
    compte_emetteur = forms.ModelChoiceField(queryset=None, empty_label="Choisir un compte", label="Compte à débiter")
    beneficiaire_iban = forms.CharField(label="Bénéficiaire (IBAN ou Nom)")
    montant = forms.DecimalField(max_digits=10, decimal_places=2)
    motif = forms.CharField(required=False)
    instantane = forms.BooleanField(required=False)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if user:
            # On ne propose que les comptes actifs de l'utilisateur
            self.fields['compte_emetteur'].queryset = Compte.objects.filter(user=user, est_actif=True)

# scoring/forms.py

class OuvrirCompteForm(forms.Form):
    # On définit les types possibles ici
    TYPE_CHOICES_BASE = [
        ('COURANT', 'Compte Courant (Standard)'),
        ('EPARGNE', 'Livret Épargne (Rémunéré)'),
        ('PRO', 'Compte Business (Pro)'),
    ]

    type_compte = forms.ChoiceField(
        choices=[], # On laisse vide ici, on va le remplir dynamiquement
        widget=forms.Select(attrs={
            'class': 'w-full p-4 rounded-xl bg-slate-50 border border-slate-200 font-bold text-slate-700 focus:ring-2 focus:ring-ice-200 focus:border-ice-400 outline-none transition-all'
        })
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # 1. On récupère les types de comptes que l'utilisateur a DÉJÀ (et qui sont actifs)
        types_existants = Compte.objects.filter(
            user=user, 
            est_actif=True
        ).values_list('type_compte', flat=True)

        # 2. On filtre la liste de base pour ne garder que ce qu'il n'a PAS encore
        choix_disponibles = [
            choix for choix in self.TYPE_CHOICES_BASE 
            if choix[0] not in types_existants
        ]

        # 3. On met à jour les choix du champ
        self.fields['type_compte'].choices = choix_disponibles

class CloturerCompteForm(forms.Form):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full p-4 rounded-xl bg-white border border-red-200 focus:border-red-500 focus:ring-red-500 text-slate-900 outline-none transition-all',
            'placeholder': 'Confirmez votre mot de passe'
        }),
        label="Votre mot de passe actuel"
    )
    
    compte_destination = forms.ModelChoiceField(
        queryset=None, 
        required=False, # Pas obligatoire si solde = 0
        widget=forms.Select(attrs={
            'class': 'w-full p-4 rounded-xl bg-white border border-slate-200 focus:border-ice-500 focus:ring-ice-500 outline-none transition-all'
        }),
        label="Transférer le solde restant vers",
        empty_label="Sélectionnez un compte (si solde > 0)"
    )
    
    confirmation = forms.BooleanField(
        required=True,
        label="Je confirme vouloir clôturer ce compte définitivement",
        widget=forms.CheckboxInput(attrs={
            'class': 'w-5 h-5 text-red-600 rounded focus:ring-red-500 border-gray-300'
        })
    )

    def __init__(self, user, compte_a_cloturer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # On propose tous les comptes actifs de l'utilisateur SAUF celui qu'on veut fermer
        if user:
            self.fields['compte_destination'].queryset = Compte.objects.filter(
                user=user, 
                est_actif=True
            ).exclude(id=compte_a_cloturer.id)

# --- CRÉDIT & SIMULATION ---

class SimulationPretForm(forms.ModelForm):
    produit = forms.ModelChoiceField(queryset=ProduitPret.objects.all(), label="Type de projet")
    emploi_snapshot = forms.ModelChoiceField(queryset=TypeEmploi.objects.all(), label="Situation Pro")
    logement_snapshot = forms.ModelChoiceField(queryset=TypeLogement.objects.all(), label="Logement")
    
    class Meta:
        model = DemandeCredit
        fields = [
            'produit', 'montant_souhaite', 'duree_souhaitee_annees', 
            'apport_personnel', 'revenus_mensuels', 'loyer_actuel', 
            'dettes_mensuelles', 'enfants_a_charge', 
            'emploi_snapshot', 'logement_snapshot', 'sante_snapshot'
        ]
        widgets = {
            'montant_souhaite': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 250000'}),
            'duree_souhaitee_annees': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 20'}),
            'apport_personnel': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Ex: 30000'}),
            'revenus_mensuels': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Net avant impôts'}),
        }
