# Banquise 

Banquise est une néobanque web (Django 4.2) : comptes, cartes, virements, abonnements, crédit avec avis automatique, notifications, support chat et console admin dédiée.

## Sommaire
1. Fonctionnalités
2. Stack technique
3. Installation
4. Arborescence
5. URLs utiles
6. Règles métiers
7. Automatisation
8. Données / Migrations
9. Tests manuels
10. Sécurité
11. Support / Contact
12. Licence
13. Contributeurs

## 1. Fonctionnalités
- Authentification, profil, tableau de bord.
- Comptes courant/épargne/pro, clôture/ouverture, relevés paginés, export PDF (si reportlab).
- Cartes : blocage/déblocage, sans-contact, paiement étranger, plafonds ; blocage auto si dépassement du découvert (Essentiel 100 €, Plus 500 €, Infinite 1000 €) et déblocage dès retour au-dessus.
- Virements SEPA, bénéficiaires enregistrés, miroir interne (IBAN normalisé : espaces/traits ignorés, insensible à la casse), notifications émetteur/destinataire.
- Abonnements Essentiel / Plus / Infinite : débit immédiat, transaction associée, notification, prochaine facturation.
- Crédit : avis automatique (score/DTI/LTV), statut en attente jusqu’à validation admin, historique.
- Notifications : centre dédié + badge avatar (virements, abonnements, crédit, support, découvert).
- Support : chat client ↔ admin avec notifications.
- Admin : dashboard custom, validation crédits, console de gestion (comptes/cartes/bénéficiaires/transactions) sans passer par l’admin Django.
- Admin Reports : heatmap dépenses, comptes à surveiller, exports + commande hebdo email.

## 2. Stack technique
- Python 3.9+, Django 4.2.25
- crispy-forms + crispy-bootstrap5, mathfilters
- SQLite par défaut, Tailwind CDN + Bootstrap Icons
- ReportLab optionnel pour PDF
- Email : backend console (`django.core.mail.backends.console.EmailBackend`) ; config SMTP en prod via `EMAIL_BACKEND` / `DEFAULT_FROM_EMAIL`.

## 3. Installation
```bash
python3 -m venv venv
source venv/bin/activate
pip install "Django==4.2.25" crispy-forms crispy-bootstrap5 django-mathfilters reportlab
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```
Variables utiles (dev) : `DJANGO_SETTINGS_MODULE=Banquise.settings`, `DEBUG=1`, `SECRET_KEY` à régénérer en prod. Basculer sur PostgreSQL pour la prod (ENGINE/NAME/USER/PASSWORD/HOST/PORT).  
Ajoute aussi les dépendances ML : `numpy`, `pandas`, `scikit-learn`, `openpyxl`, `joblib` (déjà listées dans `requirements.txt`) pour pouvoir entraîner/charger le pipeline de scoring.

## 4. Arborescence (principale)
```
Banquise/
├─ manage.py                  # Entrée Django (CLI)
├─ Banquise/                  # Config projet
│  ├─ settings.py             # Paramètres (DB, apps, sécurité, CSP, email)
│  ├─ urls.py                 # Routage racine
│  ├─ wsgi.py / asgi.py       # Entrées serveur
├─ scoring/                   # App métier
│  ├─ admin.py                # Enregistrement admin Django
│  ├─ apps.py                 # Config app
│  ├─ forms.py                # Formulaires (inscription, virement, filtre, etc.)
│  ├─ middleware.py           # Middleware sécurité (CSP, headers)
│  ├─ models.py               # Modèles (Compte, Carte, Transaction, etc.)
│  ├─ urls.py                 # Routes de l’app
│  ├─ views.py                # Vues (dashboard, virement, crédits, admin custom…)
│  ├─ ml.py                   # Chargement du pipeline ML sérialisé
│  ├─ migrations/             # Migrations base
│  └─ templatetags/           # Tags/filters personnalisés
├─ templates/                 # Templates HTML
│  ├─ base.html               # Layout principal
│  ├─ registration/           # Templates auth Django
│  └─ scoring/                # Pages app (home, dashboard, admin custom, produits, etc.)
├─ data/                      # Datasets publics (GiveMeSomeCredit, German Credit, etc.) pour le scoring ML
├─ ml/                        # Scripts d'entraînement offline (ml/train_credit_model.py)
├─ scoring/model_credit.pkl   # Pipeline ML sérialisé (à générer via `ml/train_credit_model.py`)
├─ README.md                  # Présentation et guide
└─ cahier_des_charges.tex     # Spécifications fonctionnelles/techniques
```

## 5. URLs utiles
- `/dashboard/` (Tableau de bord)
- `/simulation/` puis `/resultat/<id>/`
- `/virement/`
- `/cartes/`
- `/abonnements/`
- `/notifications/`
- `/support/chat/` (client) ; `/support/admin-chat/` (staff)
- `/console/credits/` ou `/admin/credits/` (validation crédits)
- `/console/manage/` ou `/admin/manage/` (console de gestion)
- `/admin-dashboard/`
- `/admin/` (Django admin)
- `/admin-reports/` (heatmap dépenses & comptes à surveiller)
- `/credit/<id>/` (vue détaillée d’une demande IA)

## 6. Règles métiers
- Découverts : Essentiel 100 €, Plus 500 €, Infinite 1000 € ; blocage/déblocage auto des cartes selon le seuil.
- Abonnements : débit immédiat + transaction, prochaine facturation J+30, résiliation fin de période.
- Virements internes : transaction miroir crédit, IBAN normalisé pour retrouver les comptes internes.
- Crédit : avis automatique, statut EN_ATTENTE jusqu’à action admin, notifications.


## 7. Automatisation
- Commande `python manage.py send_weekly_admin_report` : envoie hebdomadaire aux admins (comptes à surveiller + top catégories).
- Planifier cette commande via cron/cron-like (ou GitHub Actions) pour recevoir le résumé par mail chaque lundi matin.

## 8. Données / Migrations
Modèles et migrations dans `scoring/`. Si `db.sqlite3` absent : `python manage.py migrate`. Créer un compte admin pour valider les crédits et répondre au support.  
Les datasets publics (GiveMeSomeCredit, German Credit, etc.) résident dans `data/` et alimentent `ml/train_credit_model.py`. Lance par exemple :
```
python ml/train_credit_model.py --input data/GiveMeSomeCredit.xlsx --target SeriousDlqin2yrs
```
pour générer `scoring/model_credit.pkl`, qui est ensuite chargé via `scoring/ml.py` dans les simulations de crédit.

## 9. Tests manuels
- Création compte, login, profil, changement de mot de passe.
- Comptes : ouverture/clôture, relevé, PDF (si reportlab).
- Cartes : blocage/déblocage, options, blocage auto sur dépassement découvert.
- Virements interne/externe : débit + miroir interne, notifications.
- Abonnements : upgrade/downgrade, débit, résiliation fin de période.
- Crédit : simulation (avis auto), validation/refus admin, notifications.
- Support : message client, réponse admin, badge non lu.
- Console admin : actions comptes/cartes/bénéficiaires, transactions visibles.

## 10. Sécurité
- Mode démo : clé secrète en clair, pas d’e-mails/SMS réels. En prod : changer `SECRET_KEY`, désactiver `DEBUG`, activer HTTPS, 2FA/IP allowlist pour staff, externaliser statiques/médias, vérifier CSP (middleware), cookies sécurisés (SESSION/CSRF), config mail SMTP.

## 11. Support / Contact
📞 Support et contact  
Pour toute question ou assistance concernant l’installation ou l’utilisation de Banquise, contactez-nous :
- Email : nuentsa.terrel@gmail.com
- Site web : https://banquise.onrender.com

## 12. Licence
- Projet protégé par droits d’auteur. Tous droits réservés.

## 13. Contributeurs
- Terrel NUENTSA
- © 2025 Banquise. Tous droits réservés.
