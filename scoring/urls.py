from django.urls import path
from . import views

urlpatterns = [
    # --- AUTHENTIFICATION ---
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('register/confirm/', views.confirm_email, name='confirm_email'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    # --- GESTION COMPTES ---
    path('dashboard/', views.dashboard, name='dashboard'),
    path('mes-comptes/', views.gerer_comptes, name='gerer_comptes'),
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
    path('beneficiaires/modifier/<int:beneficiaire_id>/', views.modifier_beneficiaire, name='modifier_beneficiaire'),
    path('beneficiaires/supprimer/<int:beneficiaire_id>/', views.supprimer_beneficiaire, name='supprimer_beneficiaire'), # Nouvelle route

    # --- CREDIT & SIMULATION ---
    path('simulation/', views.page_simulation, name='simulation'),
    path('resultat/<int:demande_id>/', views.page_resultat, name='resultat_simulation'),
    path('resultat/<int:demande_id>/valider/', views.valider_demande_credit, name='valider_demande_credit'),
    path('demande/<int:demande_id>/supprimer/', views.supprimer_demande_credit, name='supprimer_demande_credit'),
    path('historique/', views.page_historique, name='historique'),
    path('api/calcul-pret/', views.api_calcul_pret_dynamique, name='api_calcul_pret'),
    path('changer-abonnement/', views.changer_abonnement, name='changer_abonnement'),
    path('demande-decouvert/', views.demande_decouvert, name='demande_decouvert'),

    # --- AUTRES ---
    path('support/', views.support, name='support'),
    path('profil/', views.profil, name='profil'),
    path('admin-dashboard/', views.admin_dashboard_view, name='admin_dashboard'),
    path('admin-reports/', views.admin_reports, name='admin_reports'),
    path('api/admin-stats/', views.admin_stats_api, name='admin_stats_api'),
    path('produits/comptes/', views.produits_comptes, name='produits_comptes'),
    path('produits/cartes/', views.produits_cartes, name='produits_cartes'),
    path('produits/epargne/', views.produits_epargne, name='produits_epargne'),

    # --- PAGES INFORMATIVES ---
    path('a-propos/', views.page_a_propos, name='a_propos'),
    path('tarifs/', views.page_tarifs, name='tarifs'),
    path('faq/', views.page_faq, name='faq'),
    path('carrieres/', views.page_carrieres, name='carrieres'),
    path('presse/', views.page_presse, name='presse'),
    path('partenaires/', views.page_partenaires, name='partenaires'),
    path('apis/', views.page_apis, name='apis'),
    path('mentions-legales/', views.page_mentions_legales, name='mentions_legales'),
    path('confidentialite/', views.page_confidentialite, name='confidentialite'),
    path('cookies/', views.page_cookies, name='cookies'),
    path('abonnements/', views.page_abonnements, name='abonnements'),
    path('notifications/', views.notifications_view, name='notifications'),
    path('projet-immobilier/', views.projet_immobilier, name='projet_immobilier'),

    # --- CHAT SUPPORT ---
    path('support/chat/', views.chat_support, name='chat_support'),
    path('support/admin-chat/', views.chat_support_admin, name='chat_support_admin'),
    path('console/credits/', views.admin_manage_credits, name='admin_manage_credits'),
    path('console/credits/<int:demande_id>/edit/', views.admin_edit_credit, name='admin_edit_credit'),
    # Alias pour compatibilité avec les anciens liens/templates
    path('console/credits/validation/', views.admin_manage_credits, name='admin_validation_credits'),
    path('console/manage/', views.admin_manage, name='admin_manage'),
    path('404/', views.preview_404, name='preview_404'),
    path('200/', views.preview_200, name='preview_200'),
    path('credit/<int:demande_id>/', views.demande_credit_detail, name='demande_credit_detail'),
    path('api/resultat/<int:demande_id>/update/', views.api_update_resultat, name='api_update_resultat'),
]
