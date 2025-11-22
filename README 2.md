# Banquise 2.0

Banquise est une néobanque web construite avec Django 4.2. Elle propose l’ouverture et la gestion de comptes, cartes, virements, simulation de crédit avec avis automatique, validation admin, notifications temps réel, support chat client↔admin, et un espace admin de supervision.

## Fonctionnalités principales
- Authentification, profil client, tableau de bord avec comptes, cartes actives et transactions récentes.
- Comptes courants/épargne/pro, clôture/ ouverture, relevés paginés, export PDF si *reportlab* est installé.
- Cartes : blocage/déblocage, sans-contact, paiement étranger, plafonds de retrait/paiement. Blocage automatique si découvert autorisé dépassé selon l’abonnement (Essentiel 100 €, Plus 500 €, Infinite 1000 €) et déblocage dès retour au-dessus.
- Virements SEPA, bénéficiaires enregistrés, miroir interne si IBAN Banquise, notifications émetteur/destinataire.
- Abonnements Essentiel/Plus/Infinite : débit immédiat, transaction associée, notification et prochaine facturation.
- Simulation de crédit : avis automatique (score/ration DTI/LTV) puis validation finale par un admin. Historique des demandes.
- Notifications : centre de notifications, badge sur l’avatar, alertes pour virements, changements d’abonnement, décisions crédit, messages de support, dépassement découvert.
- Support : chat client ↔ admin avec historisation et notifications. Faq/Pages vitrines (Tarifs, À propos, FAQ, etc.).
- Admin : dashboard custom (statistiques, transactions récentes, top dépenses), validation des crédits en attente, console de gestion (comptes/cartes/bénéficiaires/transactions) sans passer par l’admin Django, accès CRUD Django admin.

## Stack technique
- Python 3.9+, Django 4.2.25
- crispy-forms + crispy-bootstrap5, mathfilters
- SQLite par défaut (fichier `db.sqlite3`)
- Front basé sur Tailwind CDN + Bootstrap Icons
- ReportLab (optionnel) pour export PDF relevé/RIB

Variables utiles (dev) : `DJANGO_SETTINGS_MODULE=Banquise.settings`, `DEBUG=1`, `SECRET_KEY` à régénérer en prod. Pour la prod, basculer sur PostgreSQL et configurer les connexions (ENGINE/NAME/USER/PASSWORD/HOST/PORT).

## Installation rapide
```bash
python3 -m venv venv
source venv/bin/activate
pip install "Django==4.2.25" crispy-forms crispy-bootstrap5 django-mathfilters reportlab
python manage.py migrate
python manage.py createsuperuser  # si besoin d’un compte admin
python manage.py runserver
```

## URLs utiles
- Tableau de bord : `/dashboard/`
- Simulation crédit : `/simulation/` puis résultats `/resultat/<id>/`
- Virements : `/virement/`
- Cartes : `/cartes/`
- Abonnements : `/abonnements/`
- Notifications : `/notifications/`
- Chat support : `/support/chat/` (clients), `/support/admin-chat/` (staff)
- Validation crédits (staff) : `/console/credits/` (ou `/admin/credits/`)
- Console de gestion (staff) : `/console/manage/` (ou `/admin/manage/`)
- Dashboard admin custom : `/admin-dashboard/`
- Django admin : `/admin/`

## Règles métiers clés
- Découvert autorisé selon abonnement : Essentiel 100 €, Plus 500 €, Infinite 1000 €. Dépassement → blocage des cartes + notification; déblocage automatique quand le solde repasse au-dessus.
- Abonnement changeant : débit immédiat, transaction “Abonnement Banquise …”, prochaine facturation J+30, résiliation programmée en fin de période si demandé.
- Virements internes : création de transaction miroir crédit pour le destinataire.
- Crédit : avis automatique (IA) sur la simulation, statut reste “en attente” jusqu’à action admin. Notifications envoyées à chaque étape.

## Données/Migrations
Les modèles et migrations sont dans `scoring/`. Si la base `db.sqlite3` est absente, exécuter `python manage.py migrate`. Pensez à créer un compte admin pour valider les crédits et répondre aux messages support.

## Tests
Pas de suite de tests automatisés fournie. Pour valider manuellement : création compte, ouverture/clôture, virement interne, dépassement découvert, simulation crédit, validation admin, envoi/réponse de message support, lecture des notifications.

## Licences et sécurité
Utilisation en mode démo uniquement (clé secrète en clair, pas d’e-mails/SMS envoyés). Changer `SECRET_KEY`, désactiver `DEBUG`, configurer la base en production, activer HTTPS, protéger l’accès staff (2FA/IP allowlist), externaliser les fichiers statiques/médias, vérifier la CSP (middleware de sécurité) et les cookies sécurisés (SESSION/CSRF).
