from django.urls import path
from . import views

urlpatterns = [
    # --- AUTHENTIFICATION ---
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # --- GESTION COMPTES ---
    path('dashboard/', views.dashboard, name='dashboard'),
    path('statistiques/', views.statistiques, name='statistiques'), # Nouvelle route
    path('ouvrir-compte/', views.ouvrir_compte, name='ouvrir_compte'),
    path('fermer-compte/<int:compte_id>/', views.fermer_compte, name='fermer_compte'),
    path('releve-compte/<int:compte_id>/', views.releve_compte, name='releve_compte'),
    path('releve-compte/<int:compte_id>/pdf/', views.telecharger_releve_pdf, name='telecharger_releve_pdf'),
    path('rib-compte/<int:compte_id>/pdf/', views.telecharger_rib_pdf, name='telecharger_rib_pdf'),
    
    # --- BANQUE AU QUOTIDIEN ---
    path('cartes/', views.cartes, name='cartes'),
    path('gestion-plafonds/<int:carte_id>/', views.gestion_plafonds, name='gestion_plafonds'),
    
    # --- VIREMENTS & BENEFICIAIRES ---
    path('virement/', views.virement, name='virement'),
    path('beneficiaires/', views.gestion_beneficiaires, name='beneficiaires'), # Nouvelle route
    path('beneficiaires/nouveau/', views.ajouter_beneficiaire, name='ajouter_beneficiaire'), # Nouvelle route
    path('beneficiaires/supprimer/<int:beneficiaire_id>/', views.supprimer_beneficiaire, name='supprimer_beneficiaire'), # Nouvelle route

    # --- CREDIT & SIMULATION ---
    path('simulation/', views.page_simulation, name='simulation'),
    path('resultat/<int:demande_id>/', views.page_resultat, name='resultat_simulation'),
    path('historique/', views.page_historique, name='historique'),
    path('api/calcul-pret/', views.api_calcul_pret_dynamique, name='api_calcul_pret'),

    # --- AUTRES ---
    path('support/', views.support, name='support'),
    path('profil/', views.profil, name='profil'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('api/admin-stats/', views.admin_stats_api, name='admin_stats_api'),
    path('produits/comptes/', views.produits_comptes, name='produits_comptes'),
    path('produits/cartes/', views.produits_cartes, name='produits_cartes'),
    path('produits/epargne/', views.produits_epargne, name='produits_epargne'),
]