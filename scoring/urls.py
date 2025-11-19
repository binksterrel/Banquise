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
    path('ouvrir-compte/', views.ouvrir_compte, name='ouvrir_compte'),
    path('fermer-compte/<int:compte_id>/', views.fermer_compte, name='fermer_compte'),
    
    # === NOUVELLES ROUTES AJOUTÉES ===
    # Route pour le relevé de compte
    path('releve-compte/<int:compte_id>/', views.releve_compte, name='releve_compte'),
    # Route pour le téléchargement PDF
    path('releve-compte/<int:compte_id>/pdf/', views.telecharger_releve_pdf, name='telecharger_releve_pdf'),
    # =================================

    # --- BANQUE AU QUOTIDIEN ---
    path('cartes/', views.cartes, name='cartes'),
    path('gestion-plafonds/<int:carte_id>/', views.gestion_plafonds, name='gestion_plafonds'),
    path('virement/', views.virement, name='virement'),

    # --- CREDIT & SIMULATION ---
    path('simulation/', views.page_simulation, name='simulation'),
    path('resultat/<int:demande_id>/', views.page_resultat, name='resultat_simulation'),
    path('historique/', views.page_historique, name='historique'),
    path('api/calcul-pret/', views.api_calcul_pret_dynamique, name='api_calcul_pret'),

    # --- AUTRES ---
    path('support/', views.support, name='support'),
    path('profil/', views.profil, name='profil'),
]