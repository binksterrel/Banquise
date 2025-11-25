from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import (
    ProfilClient, Compte, Carte, Transaction, 
    DemandeCredit, ProduitPret, TypeEmploi, TypeLogement,
    Beneficiaire, DemandeDecouvert
)

# ===============================================
# 1. PERSONNALISATION DE L'ADMIN DJANGO PAR DÉFAUT
# ===============================================

# Inline pour afficher le profil directement dans la page de l'utilisateur
class ProfilClientInline(admin.StackedInline):
    model = ProfilClient
    can_delete = False
    verbose_name_plural = 'Profil Client'
    fields = ('date_de_naissance', 'ville_naissance', 'telephone')
    
# On redéfinit la classe UserAdmin pour y inclure le profil
class CustomUserAdmin(UserAdmin):
    inlines = (ProfilClientInline,)
    list_display = UserAdmin.list_display + ('get_full_name', 'is_staff', 'is_active', 'date_joined')
    list_select_related = ('profil',)


# On dé-enregistre l'User par défaut pour enregistrer notre CustomUserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


# ===============================================
# 2. GESTION DES MODÈLES FINANCIERS
# ===============================================

@admin.register(Compte)
class CompteAdmin(admin.ModelAdmin):
    list_display = ('user', 'type_compte', 'solde', 'numero_compte', 'est_actif', 'date_creation')
    list_filter = ('type_compte', 'est_actif')
    search_fields = ('numero_compte', 'user__username', 'user__email')
    raw_id_fields = ('user',) # Rendre la recherche d'utilisateur plus performante

@admin.register(Carte)
class CarteAdmin(admin.ModelAdmin):
    list_display = ('compte', 'numero_visible', 'date_expiration', 'plafond_paiement', 'est_bloquee')
    list_filter = ('est_bloquee', 'sans_contact_actif', 'paiement_etranger_actif')
    search_fields = ('compte__numero_compte', 'compte__user__username')
    # Permet de choisir le compte via une recherche plutôt qu'une liste déroulante
    raw_id_fields = ('compte',) 


@admin.register(Beneficiaire)
class BeneficiaireAdmin(admin.ModelAdmin):
    list_display = ('user', 'nom', 'iban', 'date_ajout')
    search_fields = ('nom', 'iban', 'user__username')
    raw_id_fields = ('user',)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    # Affiche la catégorie pour plus de clarté
    list_display = ('compte', 'montant', 'libelle', 'type', 'categorie', 'date_execution')
    list_filter = ('type', 'categorie', 'date_execution')
    search_fields = ('libelle', 'compte__numero_compte')
    raw_id_fields = ('compte',)
    # Permet de modifier la catégorie à posteriori pour corriger les erreurs de l'utilisateur
    fields = ('compte', 'montant', 'libelle', 'type', 'categorie', 'date_execution')


# ===============================================
# 3. GESTION DES CRÉDITS ET SCORES
# ===============================================

@admin.register(DemandeCredit)
class DemandeCreditAdmin(admin.ModelAdmin):
    list_display = ('user', 'montant_souhaite', 'duree_souhaitee_annees', 'score_calcule', 'statut', 'date_demande')
    list_filter = ('statut', 'produit__nom', 'date_demande')
    search_fields = ('user__username', 'montant_souhaite')
    raw_id_fields = ('user', 'produit', 'emploi_snapshot', 'logement_snapshot')
    # Permet de visualiser toutes les données qui ont servi à calculer le score
    fieldsets = (
        ('Informations Client', {
            'fields': ('user', 'produit', 'montant_souhaite', 'duree_souhaitee_annees', 'apport_personnel'),
        }),
        ('Situation Financière', {
            'fields': ('revenus_mensuels', 'loyer_actuel', 'dettes_mensuelles', 'enfants_a_charge'),
        }),
        ('Score et Décision', {
            'fields': ('score_calcule', 'taux_calcule', 'recommendation', 'statut', 'date_demande'),
        }),
        ('Snapshot (au moment de la demande)', {
            'fields': ('emploi_snapshot', 'logement_snapshot', 'sante_snapshot'),
            'classes': ('collapse',),
        })
    )

# Enregistrement simple des tables de référence
admin.site.register(ProduitPret)
admin.site.register(TypeEmploi)
admin.site.register(TypeLogement)


@admin.register(DemandeDecouvert)
class DemandeDecouvertAdmin(admin.ModelAdmin):
    list_display = ('user', 'montant_souhaite', 'statut', 'expire_le', 'cree_le')
    list_filter = ('statut',)
    search_fields = ('user__username',)
    raw_id_fields = ('user',)
