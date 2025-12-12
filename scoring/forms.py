from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
import re
from .models import DemandeCredit, TypeEmploi, TypeLogement, ProduitPret, Compte, Transaction, Beneficiaire, ProfilClient
from .cities import is_valid_french_city

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
    telephone = forms.CharField(label="Numéro de téléphone", max_length=20)
    email = forms.EmailField(label="Email")
    confirm_email = forms.EmailField(label="Confirmer l'email")
    password = forms.CharField(widget=forms.PasswordInput, label="Mot de passe")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirmer mot de passe")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']

    def _normalize_phone(self, value: str) -> str:
        return re.sub(r"[^0-9]", "", value or "")

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        pattern = r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$"
        if not re.match(pattern, email):
            raise ValidationError("Adresse email invalide (exemple : nom@domaine.fr).")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Un compte existe déjà avec cet email.")
        return email

    def clean_first_name(self):
        first = (self.cleaned_data.get("first_name") or "").strip()
        # Autorise lettres + espaces/tirets/apostrophes, minimum 2 caractères
        if not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]{2,50}$", first):
            raise ValidationError("Prénom invalide (lettres, espaces, tirets seulement).")
        return first

    def clean_last_name(self):
        last = (self.cleaned_data.get("last_name") or "").strip()
        if not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]{2,50}$", last):
            raise ValidationError("Nom invalide (lettres, espaces, tirets seulement).")
        return last

    def clean_telephone(self):
        raw = (self.cleaned_data.get("telephone") or "").strip()
        normalized = self._normalize_phone(raw)
        if len(normalized) != 10 or not normalized.startswith("06"):
            raise ValidationError("Numéro invalide : uniquement des mobiles français commençant par 06.")
        exists = ProfilClient.objects.filter(telephone=normalized).exists()
        if exists:
            raise ValidationError("Un compte utilise déjà ce numéro de téléphone.")
        return normalized

    def clean_password(self):
        pwd = self.cleaned_data.get("password") or ""
        if len(pwd) < 12:
            raise ValidationError("Le mot de passe doit contenir au moins 12 caractères.")
        if not re.search(r"\d", pwd):
            raise ValidationError("Le mot de passe doit contenir au moins un chiffre.")
        if not re.search(r"[^\w\s]", pwd):
            raise ValidationError("Le mot de passe doit contenir au moins un caractère spécial.")
        return pwd

    def clean_birth_date(self):
        birth = self.cleaned_data.get("birth_date")
        if not birth:
            return birth
        today = timezone.now().date()
        age = (today - birth).days // 365
        if age > 70:
            raise ValidationError("L'inscription est réservée aux moins de 70 ans.")
        return birth

    def clean_birth_city(self):
        city = (self.cleaned_data.get("birth_city") or "").strip()
        if not re.match(r"^[A-Za-zÀ-ÖØ-öø-ÿ' -]{2,100}$", city):
            raise ValidationError("Ville invalide : lettres, espaces ou tirets uniquement.")
        if not is_valid_french_city(city):
            raise ValidationError("Merci de saisir une ville française existante.")
        return city

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            self.add_error('confirm_password', "Les mots de passe ne correspondent pas.")
        if cleaned_data.get("email") != cleaned_data.get("confirm_email"):
            self.add_error('confirm_email', "Les emails ne correspondent pas.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.last_name = user.last_name.upper()
        user.first_name = user.first_name.title()
        user.email = self.cleaned_data['email'].lower()
        if commit:
            user.save()
        return user

# --- BANQUE AU QUOTIDIEN & BENEFICIAIRES ---

class BeneficiaireForm(forms.ModelForm):
    class Meta:
        model = Beneficiaire
        fields = ['nom', 'surnom', 'iban', 'telephone']
        labels = {
            'nom': 'Nom exact (comme sur la carte)',
            'surnom': 'Surnom (optionnel)',
            'iban': 'IBAN',
            'telephone': 'Numéro de téléphone (optionnel si IBAN renseigné)'
        }
    
    def _normalize_phone(self, value: str) -> str:
        return re.sub(r"[^0-9]", "", value or "")

    def clean_telephone(self):
        raw = self.cleaned_data.get('telephone') or ''
        if not raw:
            return ''
        normalized = self._normalize_phone(raw)
        if len(normalized) < 8 or len(normalized) > 15:
            raise ValidationError("Numéro de téléphone invalide (8 à 15 chiffres).")
        return normalized

    def clean_iban(self):
        iban = self.cleaned_data.get('iban')
        if iban:
            return valider_format_iban(iban)
        return ''

    def clean(self):
        cleaned = super().clean()
        iban = cleaned.get('iban')
        phone = cleaned.get('telephone')
        if not iban and not phone:
            raise ValidationError("Renseignez un IBAN ou un numéro de téléphone.")
        return cleaned

class VirementForm(forms.Form):
    compte_emetteur = forms.ModelChoiceField(queryset=None, label="Compte à débiter")
    execution_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}), label="Date d'exécution")
    recurrence = forms.ChoiceField(
        choices=[('NONE', 'Ponctuel'), ('MENSUEL', 'Mensuel')],
        required=False,
        label="Récurrence"
    )
    solde_minimum = forms.DecimalField(required=False, min_value=0, decimal_places=2, max_digits=10, label="Seuil solde minimum")
    
    # Sélectionner un bénéficiaire existant
    beneficiaire_enregistre = forms.ModelChoiceField(
        queryset=None, 
        required=False, 
        label="Bénéficiaire enregistré",
        empty_label="-- Sélectionner un bénéficiaire --"
    )
    
    # Ou saisir un nouvel IBAN
    nouveau_beneficiaire_iban = forms.CharField(
        required=False, 
        label="IBAN"
    )
    # Ou saisir un numéro de téléphone
    nouveau_beneficiaire_phone = forms.CharField(
        required=False,
        label="Numéro de téléphone"
    )
    
    montant = forms.DecimalField(min_value=0.01, decimal_places=2, label="Montant (€)")
    motif = forms.CharField(max_length=100, required=False, label="Motif (facultatif)")

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['compte_emetteur'].queryset = Compte.objects.filter(user=user, est_actif=True)
        self.fields['beneficiaire_enregistre'].queryset = Beneficiaire.objects.filter(user=user)

    def _normalize_phone(self, value: str) -> str:
        return re.sub(r"[^0-9]", "", value or "")

    def clean_nouveau_beneficiaire_phone(self):
        raw = self.cleaned_data.get('nouveau_beneficiaire_phone') or ''
        if not raw:
            return ''
        normalized = self._normalize_phone(raw)
        if len(normalized) < 8 or len(normalized) > 15:
            raise ValidationError("Numéro de téléphone invalide (8 à 15 chiffres).")
        exists = ProfilClient.objects.filter(telephone=normalized).exists()
        # Fallback si le téléphone est stocké avec des espaces/formatage
        if not exists:
            for profil in ProfilClient.objects.exclude(telephone='').only('telephone'):
                if self._normalize_phone(profil.telephone) == normalized:
                    exists = True
                    break
        if not exists:
            raise ValidationError("Aucun client Banquise trouvé avec ce numéro.")
        return normalized

    def clean_nouveau_beneficiaire_iban(self):
        iban = self.cleaned_data.get('nouveau_beneficiaire_iban')
        if iban:
            return valider_format_iban(iban)
        return ''

    def clean(self):
        cleaned_data = super().clean()
        bene = cleaned_data.get("beneficiaire_enregistre")
        iban = cleaned_data.get("nouveau_beneficiaire_iban")
        phone = cleaned_data.get("nouveau_beneficiaire_phone")
        exec_date = cleaned_data.get("execution_date")
        recurrence = cleaned_data.get("recurrence") or 'NONE'

        options = [bool(bene), bool(iban), bool(phone)]
        if not any(options):
            raise forms.ValidationError("Veuillez sélectionner un bénéficiaire, un IBAN ou un numéro de téléphone.")
        if sum(options) > 1:
            raise forms.ValidationError("Choisissez une seule option : bénéficiaire enregistré, IBAN ou téléphone.")
        
        if bene:
            cleaned_data['nouveau_beneficiaire_iban'] = None
            cleaned_data['nouveau_beneficiaire_phone'] = ''

        # Validation planification
        if exec_date and exec_date < timezone.now().date():
            raise forms.ValidationError("La date d'exécution doit être aujourd'hui ou plus tard.")
        if recurrence not in ['NONE', 'MENSUEL']:
            cleaned_data['recurrence'] = 'NONE'
        return cleaned_data

class OuvrirCompteForm(forms.Form):
    type_compte = forms.ChoiceField(choices=[], label="Type de compte")
    entreprise_nom = forms.CharField(label="Nom de l'entreprise", max_length=150, required=False)
    entreprise_siret = forms.CharField(label="SIRET / Identifiant fiscal", max_length=20, required=False)
    entreprise_contact = forms.CharField(label="Contact entreprise (email ou téléphone)", max_length=100, required=False)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        comptes_existants = Compte.objects.filter(user=user, est_actif=True).values_list('type_compte', flat=True)
        choix_possibles = [c for c in Compte.TYPE_CHOICES if c[0] not in comptes_existants]
        self.fields['type_compte'].choices = choix_possibles
        # UI hints
        self.fields['type_compte'].widget.attrs.update({'class': 'w-full rounded-xl border border-slate-200 bg-white/80 py-3 px-4 text-sm font-medium text-slate-800'})
        self.fields['entreprise_nom'].widget.attrs.update({'class': 'w-full rounded-xl border border-slate-200 bg-white/80 py-3 px-4 text-sm font-medium text-slate-800', 'placeholder': "Acme SAS"})
        self.fields['entreprise_siret'].widget.attrs.update({'class': 'w-full rounded-xl border border-slate-200 bg-white/80 py-3 px-4 text-sm font-medium text-slate-800', 'placeholder': "SIRET / TVA / N° fiscal"})
        self.fields['entreprise_contact'].widget.attrs.update({'class': 'w-full rounded-xl border border-slate-200 bg-white/80 py-3 px-4 text-sm font-medium text-slate-800', 'placeholder': "contact@entreprise.fr ou +33..."})

    def clean(self):
        cleaned = super().clean()
        type_compte = cleaned.get('type_compte')
        if type_compte == 'PRO':
            nom = (cleaned.get('entreprise_nom') or '').strip()
            siret = (cleaned.get('entreprise_siret') or '').replace(' ', '')
            contact = (cleaned.get('entreprise_contact') or '').strip()
            if not nom:
                self.add_error('entreprise_nom', "Obligatoire pour un compte pro.")
            if not siret or not siret.isdigit() or len(siret) < 9 or len(siret) > 14:
                self.add_error('entreprise_siret', "SIRET/identifiant doit contenir 9 à 14 chiffres.")
            if not contact:
                self.add_error('entreprise_contact', "Contact (email ou téléphone) requis.")
            else:
                # Email simple ou numéro
                if '@' in contact:
                    if not re.match(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$", contact):
                        self.add_error('entreprise_contact', "Email de contact invalide.")
                else:
                    digits = re.sub(r"[^0-9]", "", contact)
                    if len(digits) < 8 or len(digits) > 15:
                        self.add_error('entreprise_contact', "Téléphone de contact invalide (8 à 15 chiffres).")
        return cleaned

class CloturerCompteForm(forms.Form):
    compte_destination = forms.ModelChoiceField(queryset=None, label="Virer le solde restant vers", required=False)
    password = forms.CharField(widget=forms.PasswordInput, label="Confirmez avec votre mot de passe")

    def __init__(self, user, compte_a_fermer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['compte_destination'].queryset = Compte.objects.filter(user=user, est_actif=True).exclude(id=compte_a_fermer.id)
        self.fields['compte_destination'].widget.attrs.update({
            'class': 'w-full rounded-xl border border-amber-200 bg-white/80 py-3 px-4 pr-10 text-sm font-medium text-slate-800'
        })
        self.fields['password'].widget.attrs.update({
            'class': 'w-full rounded-xl border border-slate-200 bg-white/80 py-3 px-4 pr-10 text-sm font-medium text-slate-800',
            'placeholder': 'Votre mot de passe'
        })

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
    revenus_mensuels = forms.IntegerField(label="Vos revenus mensuels nets (€)", min_value=0)
    loyer_actuel = forms.IntegerField(label="Loyer actuel / Charges (€)", required=False, min_value=0)
    dettes_mensuelles = forms.IntegerField(label="Autres crédits en cours (€)", required=False, min_value=0)
    jour_prelevement = forms.IntegerField(label="Jour souhaité de prélèvement", min_value=1, max_value=28, initial=5)
    compte_versement = forms.ModelChoiceField(queryset=Compte.objects.none(), label="Compte à créditer", required=True)
    
    class Meta:
        model = DemandeCredit
        exclude = [
            'user', 'statut', 'date_demande',
            'score_calcule', 'taux_calcule', 'recommendation',
            'sante_snapshot', 'ia_decision', 'mensualite_calculee',
            'echeances_payees', 'dernier_prelevement', 'date_acceptation'
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['compte_versement'].queryset = Compte.objects.filter(user=self.user, est_actif=True)
            self.fields['compte_versement'].empty_label = "Sélectionnez un compte"
            if not self.fields['compte_versement'].queryset.exists():
                self.fields['compte_versement'].help_text = "Aucun compte actif détecté. Ouvrez un compte pour recevoir les fonds."
        if 'compte_versement' in self.fields:
            self.fields['compte_versement'].widget.attrs.update({
                'required': 'required'
            })
        numeric_fields = [
            ('montant_souhaite', 1, 1),
            ('duree_souhaitee_annees', 1, 1),
            ('apport_personnel', 0, 1),
            ('revenus_mensuels', 1, 1),
            ('loyer_actuel', 0, 1),
            ('dettes_mensuelles', 0, 1),
            ('enfants_a_charge', 0, 1),
            ('jour_prelevement', 1, 1),
        ]
        for field_name, min_val, step in numeric_fields:
            if field_name in self.fields:
                field = self.fields[field_name]
                field.widget.attrs.update({
                    'min': min_val,
                    'step': step,
                    'type': 'number',
                    'inputmode': 'decimal',
                    'pattern': '[0-9]*',
                    'oninput': 'this.value=this.value.replace(/[^0-9]/g,"")',
                })
                # Assure la validation côté serveur
                if hasattr(field, 'min_value') and field.min_value is None:
                    field.min_value = min_val
        if 'produit' in self.fields:
            self.fields['produit'].required = True
            self.fields['produit'].empty_label = "Sélectionnez un produit"
        if 'emploi_snapshot' in self.fields:
            self.fields['emploi_snapshot'].required = True
            self.fields['emploi_snapshot'].empty_label = "Sélectionnez votre situation professionnelle"
        if 'logement_snapshot' in self.fields:
            self.fields['logement_snapshot'].required = True
            self.fields['logement_snapshot'].empty_label = "Sélectionnez votre logement"
        if 'soumise' in self.fields:
            self.fields['soumise'].label = "Soumettre la simulation"
            self.fields['soumise'].help_text = "Si vous cochez cette case, la simulation sera transmise à un conseiller."
            self.fields['soumise'].widget.attrs.update({
                'class': 'toggle-input sr-only'
            })

    def clean(self):
        cleaned = super().clean()
        checks = [
            ('montant_souhaite', 1, "Le montant souhaité doit être positif."),
            ('duree_souhaitee_annees', 1, "La durée doit être au moins de 1 an."),
            ('apport_personnel', 0, "L'apport ne peut pas être négatif."),
            ('revenus_mensuels', 1, "Les revenus doivent être positifs."),
            ('loyer_actuel', 0, "Le loyer/charges ne peut pas être négatif."),
            ('dettes_mensuelles', 0, "Les dettes mensuelles ne peuvent pas être négatives."),
            ('enfants_a_charge', 0, "Le nombre d'enfants doit être positif."),
            ('jour_prelevement', 1, "Le jour de prélèvement doit être entre 1 et 28."),
        ]
        for field, min_val, msg in checks:
            val = cleaned.get(field)
            if val is not None and val < min_val:
                self.add_error(field, msg)
        if not cleaned.get('produit'):
            self.add_error('produit', "Sélectionnez un produit avant de lancer la simulation.")
        if not cleaned.get('emploi_snapshot'):
            self.add_error('emploi_snapshot', "Sélectionnez votre situation professionnelle.")
        if not cleaned.get('logement_snapshot'):
            self.add_error('logement_snapshot', "Sélectionnez votre situation de logement.")
        compte_choice = cleaned.get('compte_versement')
        if not compte_choice:
            self.add_error('compte_versement', "Choisissez le compte sur lequel verser les fonds.")
        return cleaned
