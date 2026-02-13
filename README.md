# Banquise

**Banquise** est une néobanque web complète développée avec Django 4.2. Elle propose : gestion de comptes, cartes bancaires, virements SEPA, abonnements, crédit avec scoring IA, notifications temps réel, support chat et console d'administration dédiée.

---

## 📋 Sommaire
1. [Fonctionnalités](#1-fonctionnalités)
2. [Stack technique](#2-stack-technique)
3. [Installation](#3-installation)
4. [Arborescence](#4-arborescence) 
5. [URLs utiles](#5-urls-utiles)
6. [Règles métiers](#6-règles-métiers)
7. [Système de Crédit & IA](#7-système-de-crédit--ia)
8. [Automatisation](#8-automatisation)
9. [Données / Migrations](#9-données--migrations)
10. [Tests manuels](#10-tests-manuels)
11. [Sécurité](#11-sécurité)
12. [Support / Contact](#12-support--contact)
13. [Licence](#13-licence)

---

## 1. Fonctionnalités

### 🏦 Banque au quotidien
- **Authentification** : Inscription, connexion, profil, changement de mot de passe.
- **Comptes** : Courant / Épargne / Pro, ouverture/clôture, relevés paginés, export PDF.
- **Cartes** : Blocage/déblocage, sans-contact, paiement étranger, plafonds personnalisés.
- **Virements SEPA** : Bénéficiaires enregistrés, miroir interne (IBAN normalisé), virements programmés.

### 💳 Abonnements
- Formules **Essentiel** (gratuit), **Plus** (9,90€), **Infinite** (19,90€).
- Débit immédiat, transaction associée, notification, prochaine facturation J+30.
- Découvert autorisé selon formule : 100€ / 500€ / 1000€.

### 📊 Crédit & Scoring IA
- Simulation de crédit avec **scoring automatique** (Random Forest).
- Règles métier strictes : DTI < 45%, Reste-à-vivre, Solvabilité.
- **Suggestion intelligente** : Proposition de mensualité/durée optimisées si refus.
- Calculs financiers rigoureux (formule PMT actuarielle, NPER pour suggestions).

### 🔔 Notifications & Support
- Centre de notifications unifié (virements, abonnements, crédit, découvert).
- Chat support client ↔ admin avec badge non-lu.

### ⚙️ Administration
- Dashboard custom, validation crédits, console de gestion (comptes/cartes/bénéficiaires).
- Rapports admin : heatmap dépenses, comptes à surveiller, exports.
- Commande hebdomadaire email (`send_weekly_admin_report`).

### 🚨 Alertes & Actions Rapides
- Page `/alertes/` : Comptes avec solde bas, prélèvements crédit à venir, virements programmés.
- Bouton "Approvisionner" pré-remplit l'IBAN sur la page virement.

---

## 2. Stack technique

| Catégorie | Technologies |
|-----------|--------------|
| Backend | Python 3.9+, Django 4.2 |
| Frontend | Tailwind CSS (CDN), Bootstrap Icons |
| Formulaires | crispy-forms + crispy-bootstrap5, mathfilters |
| Base de données | SQLite (dev), PostgreSQL (prod recommandé) |
| ML / Data Science | scikit-learn, pandas, numpy, joblib |
| PDF | ReportLab (optionnel) |
| Email | Console backend (dev), SMTP (prod) |

---

## 3. Installation

```bash
# Cloner le projet
git clone https://github.com/binksterrel/Banquise.git
cd Banquise

# Environnement virtuel
python3 -m venv venv
source venv/bin/activate

# Dépendances
pip install -r requirements.txt
# Ou manuellement :
# pip install Django==4.2.25 crispy-forms crispy-bootstrap5 django-mathfilters reportlab numpy pandas scikit-learn joblib

# Migrations
python manage.py migrate

# Créer un superutilisateur
python manage.py createsuperuser

# Entraîner le modèle ML (optionnel, un modèle pré-entraîné est fourni)
python manage.py train_credit_model

# Lancer le serveur
python manage.py runserver
```

### Variables d'environnement (prod)
```bash
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=0
DJANGO_ALLOWED_HOSTS=yourdomain.com
DATABASE_URL=postgres://...
EMAIL_HOST=smtp.example.com
EMAIL_PORT=587
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
```

---

## 4. Arborescence

```
Banquise/
├── manage.py                     # Entrée Django (CLI)
├── requirements.txt              # Dépendances Python
├── Procfile                      # Config Render/Heroku
├── db.sqlite3                    # Base SQLite (dev)
├── demandes_credits.log          # Log des simulations (audit)
├── README.md                     # Ce fichier
├── cahier_des_charges.tex        # Spécifications fonctionnelles
│
├── Banquise/                     # Config projet Django
│   ├── settings.py               # Paramètres (DB, apps, sécurité, email, logging)
│   ├── urls.py                   # Routage racine
│   └── wsgi.py / asgi.py         # Entrées serveur
│
├── scoring/                      # App métier principale
│   ├── models.py                 # Modèles (Compte, Carte, Transaction, DemandeCredit...)
│   ├── views.py                  # Vues (dashboard, virement, crédits, admin custom…)
│   ├── forms.py                  # Formulaires (inscription, virement, simulation...)
│   ├── urls.py                   # Routes de l'app
│   ├── admin.py                  # Enregistrement admin Django
│   ├── ml.py                     # Chargement du pipeline ML sérialisé
│   ├── model_credit.pkl          # Pipeline ML sérialisé (Random Forest)
│   ├── utils.py                  # Fonctions utilitaires
│   ├── cities.py                 # Données villes (autocomplétion)
│   ├── context_processors.py     # Processeurs de contexte Django
│   ├── middleware.py             # Middleware sécurité (CSP, headers)
│   ├── management/               # Commandes Django custom
│   │   └── commands/
│   │       ├── train_credit_model.py       # Entraînement ML
│   │       └── send_weekly_admin_report.py # Rapport hebdo admin
│   ├── migrations/               # Migrations base de données
│   ├── static/                   # Fichiers statiques (CSS, JS)
│   ├── templatetags/             # Tags/filters personnalisés
│   └── tests/                    # Tests unitaires
│       ├── test_rigorous_logic.py
│       └── ...
│
├── templates/                    # Templates HTML
│   ├── base.html                 # Layout principal
│   ├── registration/             # Templates auth Django
│   └── scoring/                  # Pages app
│       ├── dashboard.html
│       ├── virement.html
│       ├── resultat.html
│       ├── historique.html
│       ├── alertes.html
│       └── ...
│
├── data/                         # Dataset d'entraînement
│   └── loan_prediction_dataset.csv
│
├── ml/                           # Scripts d'entraînement ML
│   └── train_credit_model.py     # python ml/train_credit_model.py
│
└── scripts/                      # Scripts utilitaires
```

---

## 5. URLs utiles

| URL | Description |
|-----|-------------|
| `/dashboard/` | Tableau de bord principal |
| `/simulation/` | Nouvelle simulation de crédit |
| `/resultat/<id>/` | Résultat d'une simulation |
| `/virement/` | Effectuer un virement |
| `/cartes/` | Gestion des cartes |
| `/abonnements/` | Changer de formule |
| `/alertes/` | Actions rapides & rappels |
| `/notifications/` | Centre de notifications |
| `/historique/` | Historique des demandes de crédit |
| `/support/chat/` | Chat support (client) |
| `/support/admin-chat/` | Chat support (staff) |
| `/console/credits/` | Validation des crédits (admin) |
| `/console/manage/` | Console de gestion (admin) |
| `/admin-dashboard/` | Dashboard admin |
| `/admin-reports/` | Rapports & statistiques |
| `/admin/` | Django admin natif |

---

## 6. Règles métiers

### Découverts
| Formule | Limite découvert | Blocage auto carte |
|---------|------------------|-------------------|
| Essentiel | 100 € | Oui |
| Plus | 500 € | Oui |
| Infinite | 1000 € | Oui |

### Abonnements
- Débit immédiat à l'upgrade, transaction associée.
- Prochaine facturation : J+30.
- Résiliation : fin de période (pas de remboursement prorata).

### Virements
- Internes : transaction miroir crédit automatique.
- IBAN normalisé : espaces/traits ignorés, insensible à la casse.

---

## 7. Système de Crédit & IA

### Pipeline de décision (3 couches)

1. **Hard Rules (Règles absolues)**
   - DTI (Taux d'endettement) ≤ 45%
   - Reste-à-vivre ≥ 800€ + 300€/enfant
   - Mensualité couvre au minimum le capital

2. **Scoring IA (Random Forest)**
   - Features : revenus, montant, durée, historique crédit, personnes à charge...
   - Score 0-100, seuil d'acceptation : 50

3. **Policy Adjustments**
   - Bonus : Bon état de santé (+5), Apport ≥ 10% (+10), DTI < 35% (+15)

### Moteur de suggestion
Si refus, le système propose une **configuration optimisée** :
- Calcul actuariel exact (formule NPER) pour trouver la durée idéale.
- Cible un DTI de 33% pour garantir l'acceptation.

### Logging (Audit)
Chaque simulation est enregistrée dans `demandes_credits.log` :
```
2024-12-14 14:15:00 [INFO] SIMULATION | User: john | Montant: 50000€ | Durée: 15 ans | Score: 72 | Décision IA: ACCEPTEE
```

---

## 8. Automatisation

```bash
# Rapport hebdomadaire admin (cron recommandé le lundi 8h)
python manage.py send_weekly_admin_report

# Entraîner le modèle ML
python manage.py train_credit_model
```

---

## 9. Données / Migrations

```bash
# Appliquer les migrations
python manage.py migrate

# Créer un compte admin
python manage.py createsuperuser
```

Le dataset d'entraînement (`data/loan_prediction_dataset.csv`) est inclus. Le modèle pré-entraîné (`scoring/model_credit.pkl`) est prêt à l'emploi.

---

## 10. Tests manuels

- [ ] Création compte, login, profil, changement de mot de passe
- [ ] Comptes : ouverture/clôture, relevé, PDF
- [ ] Cartes : blocage/déblocage, options, blocage auto sur découvert
- [ ] Virements interne/externe : débit + miroir, notifications
- [ ] Virements programmés : création, pause, reprise, suppression
- [ ] Abonnements : upgrade/downgrade, débit, résiliation
- [ ] Crédit : simulation, avis auto, application suggestion, validation admin
- [ ] Support : message client, réponse admin, badge non lu
- [ ] Console admin : actions comptes/cartes/bénéficiaires

---

## 11. Sécurité

> ⚠️ **Mode démo** : Clé secrète en clair, pas d'e-mails réels.

### Checklist production
- [ ] Changer `SECRET_KEY`
- [ ] Mettre `DEBUG=0`
- [ ] Activer HTTPS (certificat SSL)
- [ ] Configurer SMTP réel
- [ ] Migrer vers PostgreSQL
- [ ] Vérifier CSP (middleware)
- [ ] Cookies sécurisés (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`)
- [ ] 2FA / IP allowlist pour staff

---

## 12. Support / Contact

📧 **Email** : nuentsa.terrel@gmail.com  
🌐 **Site web** : [banquise.onrender.com](https://banquise.onrender.com)

---

## 13. Licence

© 2025 Banquise. Tous droits réservés.  
Projet protégé par droits d'auteur.

**Développé par** : Terrel NUENTSA
