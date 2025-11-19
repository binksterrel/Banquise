from django.contrib import admin
from .models import (
    ProfilClient, 
    Compte, 
    Carte, 
    Transaction, 
    DemandeCredit, 
    ProduitPret, 
    TypeEmploi, 
    TypeLogement
)

# --- Paramètres Simples ---
admin.site.register(TypeEmploi)
admin.site.register(TypeLogement)
admin.site.register(ProduitPret)

# --- Clients & Profils ---
@admin.register(ProfilClient)
class ProfilClientAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_de_naissance', 'telephone', 'ville_naissance')
    search_fields = ('user__username', 'user__email', 'telephone')

# --- Comptes Bancaires ---
@admin.register(Compte)
class CompteAdmin(admin.ModelAdmin):
    list_display = ('numero_compte', 'user', 'type_compte', 'solde', 'date_creation')
    list_filter = ('type_compte', 'date_creation')
    search_fields = ('numero_compte', 'user__username')
    ordering = ('-date_creation',)

# --- Cartes Bancaires ---
@admin.register(Carte)
class CarteAdmin(admin.ModelAdmin):
    list_display = ('numero_visible', 'compte', 'date_expiration', 'est_bloquee', 'plafond_paiement', 'plafond_retrait')
    list_filter = ('est_bloquee', 'date_expiration')
    search_fields = ('numero_visible', 'compte__user__username')
    
    actions = ['bloquer_cartes', 'debloquer_cartes']

    def bloquer_cartes(self, request, queryset):
        queryset.update(est_bloquee=True)
    bloquer_cartes.short_description = "Bloquer les cartes sélectionnées"

    def debloquer_cartes(self, request, queryset):
        queryset.update(est_bloquee=False)
    debloquer_cartes.short_description = "Débloquer les cartes sélectionnées"

# --- Transactions ---
@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('date_execution', 'compte', 'montant', 'type', 'libelle')
    list_filter = ('type', 'date_execution')
    search_fields = ('libelle', 'compte__numero_compte')
    ordering = ('-date_execution',)

# --- Crédits & Simulations ---
@admin.register(DemandeCredit)
class DemandeCreditAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'produit', 'montant_souhaite', 
        'score_calcule', 'statut', 'date_demande'
    )
    list_filter = ('statut', 'produit', 'date_demande')
    search_fields = ('user__username', 'id')
    readonly_fields = ('score_calcule', 'taux_calcule', 'recommendation', 'date_demande')

    # Actions personnalisées pour les conseillers
    actions = ['approuver_demandes', 'refuser_demandes']

    def approuver_demandes(self, request, queryset):
        queryset.update(statut='ACCEPTEE')
    approuver_demandes.short_description = "Approuver les demandes sélectionnées"

    def refuser_demandes(self, request, queryset):
        queryset.update(statut='REFUSEE')
    refuser_demandes.short_description = "Refuser les demandes sélectionnées"