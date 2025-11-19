from django.urls import path
from . import views

urlpatterns = [
    # --- AUTHENTIFICATION ---
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # --- GESTION COMPTES (Dashboard, Ouvrir, Fermer) ---
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # C'est ici que ça changeait : on utilise ouvrir_compte maintenant
    path('ouvrir-compte/', views.ouvrir_compte, name='ouvrir_compte'),
    
    # La nouvelle route pour fermer un compte
    path('fermer-compte/<int:compte_id>/', views.fermer_compte, name='fermer_compte'),

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