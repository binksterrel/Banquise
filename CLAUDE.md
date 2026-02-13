# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Banquise is a full-featured neobanking web application (French) built with Django 4.2. It includes banking operations (accounts, cards, SEPA transfers), AI-powered credit scoring (Random Forest), real-time notifications, admin console, support chat, and subscription tiers (Essentiel/Plus/Infinite).

## Common Commands

```bash
# Run the development server
python manage.py runserver

# Run all tests
python manage.py test

# Run a single test file
python manage.py test scoring.tests.test_views

# Run a single test case
python manage.py test scoring.tests.test_views.VirementViewTest

# Run migrations
python manage.py migrate

# Create migrations after model changes
python manage.py makemigrations scoring

# Retrain the ML credit model
python manage.py train_credit_model

# Lint checks (must pass in CI)
black --check .
isort --check-only .

# Fix lint issues
black .
isort .
```

## CI Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on pushes to main/master and PRs:
1. Install deps from `requirements.txt` (Python 3.11)
2. Run `black --check` and `isort --check-only`
3. Run migrations
4. Run full test suite

## Architecture

### Single Django App: `scoring/`

All business logic lives in one app. The project uses a services layer pattern:

- **`scoring/services/banking.py`** — Transfer execution (atomic, with deadlock prevention), IBAN/phone normalization, overdraft enforcement (auto-blocks cards when over limit)
- **`scoring/services/scoring.py`** — Credit evaluation pipeline: hard rules first (DTI > 45% → reject, reste à vivre < 800€ + 300€/child → reject), then ML scoring, then policy adjustments
- **`scoring/services/notifications.py`** — Notification creation wrapper
- **`scoring/ml.py`** — Loads pre-trained Random Forest from `model_credit.pkl` (cached with `@lru_cache`), converts form data to feature vectors, returns score 0-100
- **`scoring/utils.py`** — Overdraft limit calculation by subscription tier
- **`scoring/views.py`** — All view handlers (~2700 lines, monolithic)
- **`scoring/forms.py`** — All Django forms with validation (registration, transfers, credit simulation)

### ML Pipeline

- Training script: `ml/train_credit_model.py` (also available as management command)
- Dataset: `data/loan_prediction_dataset.csv`
- Model artifact: `scoring/model_credit.pkl`
- Features: revenus, montant, duree, historique_credit, personnes_a_charge, marie, diplome, independant, dti, ratio_montant_revenus

### Key Business Rules

- **Credit scoring**: Hard rules → ML prediction → Policy bonuses (health +5, apport ≥10% +10, DTI <35% +15). Decision threshold: score ≥ 50
- **Financial formulas**: Mensualité = `P × r / (1 - (1+r)^-n)` at 3.5% annual rate
- **Overdraft limits**: Essentiel=100€, Plus=500€, Infinite=1000€ (boosted by accepted DemandeDecouvert)
- **Transfers**: Operation ID for idempotency, internal transfers create mirror credit transactions

### Configuration

- `ConfigurationGlobale` model: singleton holding DTI threshold (45%), reference rate (3.5%), minimum subsistence (800€)
- Settings toggle debug via `DJANGO_DEBUG` env var (defaults to "1")
- Timezone: Europe/Paris, Language: fr-fr

### Templates

All templates are in `templates/` at project root (not inside the app). Base layout is `templates/base.html`. Frontend uses Tailwind CSS (CDN) + Bootstrap Icons + Crispy Forms.

### Database

SQLite in development. 26 migrations in `scoring/migrations/`. Key models: `ProfilClient`, `Compte`, `Carte`, `Transaction`, `Beneficiaire`, `VirementProgramme`, `DemandeCredit`, `DemandeDecouvert`, `MessageSupport`, `Notification`.

### Deployment

Deployed on Render via Gunicorn (`Procfile`). Static files served by WhiteNoise.
