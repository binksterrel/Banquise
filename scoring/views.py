from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required 
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.core.mail import send_mail
from django.db import transaction, models
from django.db.models import Sum, F, Q
import csv
from django.core.paginator import Paginator
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta, datetime
from decimal import Decimal, ROUND_HALF_UP
from math import exp, log, ceil
import random
import io
import json
import re
import csv

# Imports pour PDF (ReportLab)
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

from .forms import (
    InscriptionForm, VirementForm, SimulationPretForm, 
    OuvrirCompteForm, CloturerCompteForm, TransactionFilterForm,
    BeneficiaireForm
)
from .models import (
    Compte, Carte, Transaction, DemandeCredit, ProfilClient, ProduitPret,
    Beneficiaire, MessageSupport, Notification, DemandeDecouvert
)
from .utils import overdraft_limit_for_user
from .ml import predict_credit, is_model_available, ModelNotLoaded

# BIC Statique pour la démo
BANQUISE_BIC = "BANQFR76"

PLAN_CONFIG = {
    'ESSENTIEL': {'prix': Decimal("0.00"), 'label': 'Essentiel'},
    'PLUS': {'prix': Decimal("9.90"), 'label': 'Plus'},
    'INFINITE': {'prix': Decimal("19.90"), 'label': 'Infinite'},
}

def notifier(user, titre, contenu, type_evt='INFO', url=''):
    Notification.objects.create(
        user=user,
        titre=titre,
        contenu=contenu,
        type=type_evt,
        url=url or ''
    )


def normalize_iban(value: str) -> str:
    return re.sub(r"[\s-]+", "", (value or "")).upper()


def find_account_by_iban(iban_norm: str):
    """Recherche insensible aux espaces/majuscules."""
    for c in Compte.objects.all():
        if normalize_iban(c.numero_compte) == iban_norm:
            return c
    return None


def custom_404(request, exception):
    return render(request, 'scoring/404.html', status=404)


def months_diff(d1, d2):
    return (d1.year - d2.year) * 12 + (d1.month - d2.month)


def custom_200(request):
    return render(request, 'scoring/200.html', status=200)


def preview_404(request):
    return render(request, 'scoring/404.html', status=404)


def preview_200(request):
    return render(request, 'scoring/200.html', status=200)



def enforce_overdraft(compte):
    """Blocage/déblocage des cartes en fonction du découvert autorisé."""
    limit = overdraft_limit_for_user(compte.user)
    solsous = compte.solde
    cartes = Carte.objects.filter(compte=compte)

    # Alerte préventive quand on approche du seuil de blocage
    seuil_alerte = -limit * Decimal("0.8")
    if solsous <= seuil_alerte:
        recent_alert = Notification.objects.filter(
            user=compte.user,
            titre__icontains="Alerte découvert",
            date_creation__gte=timezone.now() - timedelta(hours=12)
        ).exists()
        if not recent_alert:
            notifier(
                compte.user,
                "Alerte découvert",
                f"Votre solde ({solsous} €) s'approche de la limite autorisée ({-limit} €).",
                "INFO",
                url=reverse('dashboard')
            )

    if solsous < -limit:
        # Blocage si pas déjà bloqué
        updated = cartes.filter(est_bloquee=False).update(est_bloquee=True)
        if updated:
            notifier(compte.user, "Découvert dépassé", "Vos cartes sont bloquées jusqu'au retour en dessous du découvert autorisé.", "TRANSACTION", url=reverse('cartes'))
    else:
        # Déblocage si le compte est revenu au-dessus du découvert autorisé
        updated = cartes.filter(est_bloquee=True).update(est_bloquee=False)
        if updated:
            notifier(compte.user, "Cartes débloquées", "Votre solde est revenu au-dessus du découvert autorisé.", "TRANSACTION", url=reverse('cartes'))

# ==============================================================================
# 1. AUTHENTIFICATION
# ==============================================================================

def home(request):
    unread_notifs = 0
    if request.user.is_authenticated:
        unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()
    return render(request, 'scoring/home.html', {'unread_notifs': unread_notifs})

def register(request):
    pending_user_id = request.session.get('pending_user_id')
    pending_code = request.session.get('pending_email_code')
    pending_email = request.session.get('pending_email')
    pending_birth_date = request.session.get('pending_birth_date')
    pending_birth_city = request.session.get('pending_birth_city')
    awaiting_code = bool(pending_user_id and pending_code)
    if awaiting_code and not pending_email:
        try:
            pending_email = User.objects.get(id=pending_user_id).email
        except User.DoesNotExist:
            awaiting_code = False

    def _send_confirmation_code(user):
        code = f"{random.randint(100000, 999999)}"
        request.session['pending_user_id'] = user.id
        request.session['pending_email_code'] = code
        request.session['pending_code_sent_at'] = timezone.now().isoformat()
        request.session['pending_email'] = user.email
        try:
            # Email HTML stylisé
            subject = "Banquise - Code de confirmation"
            message_text = f"Votre code de vérification est : {code}"
            html_message = f"""
            <div style="background:#f8fafc;padding:32px;font-family:'Plus Jakarta Sans',Arial,sans-serif;color:#0f172a;">
              <div style="max-width:560px;margin:auto;border:1px solid #e2e8f0;border-radius:24px;overflow:hidden;background:white;box-shadow:0 18px 45px rgba(8,47,73,0.15);">
                <div style="padding:22px 24px;background:linear-gradient(135deg,#0ea5e9,#6366f1);color:white;display:flex;align-items:center;justify-content:space-between;gap:12px;">
                  <div style="display:flex;align-items:center;gap:12px;font-weight:800;font-size:19px;letter-spacing:0.6px;">
                    <span style="display:inline-flex;width:42px;height:42px;border-radius:14px;background:rgba(255,255,255,0.15);border:1px solid rgba(255,255,255,0.3);align-items:center;justify-content:center;font-size:20px;color:white;">❄️</span>
                    <span style="text-transform:uppercase;color:white;">BANQUISE</span>
                  </div>
                  <span style="padding:8px 12px;border-radius:999px;border:1px solid rgba(255,255,255,0.4);font-weight:700;font-size:12px;letter-spacing:0.1em;">Sécurité</span>
                </div>
                <div style="padding:28px;">
                  <p style="font-size:14px;font-weight:700;color:#0ea5e9;margin:0 0 6px;letter-spacing:0.08em;text-transform:uppercase;">Code de confirmation</p>
                  <h2 style="margin:0 0 12px;font-size:24px;font-weight:800;color:#0f172a;line-height:1.3;">Activez votre compte Banquise</h2>
                  <p style="font-size:15px;line-height:1.6;margin:0 0 16px;">Bonjour {user.first_name or user.username}, voici votre code de vérification pour sécuriser votre inscription.</p>
                  <div style="text-align:center;margin:26px 0;">
                    <span style="display:inline-block;font-size:30px;font-weight:800;letter-spacing:10px;padding:18px 26px;border-radius:18px;background:#e0f2fe;color:#0ea5e9;border:1px solid #bae6fd;box-shadow:0 12px 25px rgba(14,165,233,0.18);">{code}</span>
                  </div>
                  <p style="font-size:13px;line-height:1.6;margin:0 0 14px;color:#475569;text-align:center;">Valide pendant 10 minutes. Si vous n'êtes pas à l'origine de cette demande, ignorez cet email.</p>
                  <div style="margin-top:22px;padding:16px 18px;border-radius:14px;background:#f8fafc;border:1px solid #e2e8f0;display:flex;gap:12px;align-items:flex-start;">
                    <span style="width:34px;height:34px;border-radius:10px;background:#e0f2fe;color:#0ea5e9;display:inline-flex;align-items:center;justify-content:center;font-weight:800;">i</span>
                    <div>
                      <p style="margin:0;font-size:12px;font-weight:800;color:#0ea5e9;letter-spacing:0.08em;text-transform:uppercase;">Support Banquise</p>
                      <p style="margin:4px 0 0;font-size:13px;color:#475569;">Besoin d'aide ? Répondez à cet email ou ouvrez le chat support depuis l'app.</p>
                    </div>
                  </div>
                </div>
                <div style="background:#0f172a;color:white;padding:14px 24px;font-size:12px;text-align:center;letter-spacing:0.04em;">
                  Banquise • Banque nouvelle génération • www.banquise.com
                </div>
              </div>
            </div>
            """
            send_mail(
                subject,
                message_text,
                "no-reply@banquise.demo",
                [user.email],
                fail_silently=True,
                html_message=html_message
            )
        except Exception:
            pass

    def _activate_user_and_create_accounts(user):
        user.is_active = True
        user.save(update_fields=['is_active'])
        try:
            birth_date = timezone.datetime.fromisoformat(pending_birth_date).date() if pending_birth_date else None
        except Exception:
            birth_date = None
        birth_city = pending_birth_city or ""
        ProfilClient.objects.get_or_create(
            user=user,
            defaults={
                'date_de_naissance': birth_date,
                'ville_naissance': birth_city,
                'abonnement': 'ESSENTIEL',
                'prochaine_facturation': timezone.now().date() + timedelta(days=30)
            }
        )
        if not Compte.objects.filter(user=user).exists():
            compte = Compte.objects.create(
                user=user,
                type_compte='COURANT',
                solde=100.00,
                numero_compte=f"FR76{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}",
                est_actif=True
            )
            Carte.objects.create(
                compte=compte,
                numero_visible=str(random.randint(1000,9999)),
                date_expiration=timezone.now()+timedelta(days=365*4),
                est_bloquee=False,
                sans_contact_actif=True,
                paiement_etranger_actif=False
            )
            Transaction.objects.create(
                compte=compte,
                montant=100.00,
                libelle="Cadeau de bienvenue Banquise",
                type='CREDIT',
                categorie='SALAIRE'
            )

        # Nettoyage session
        request.session.pop('pending_user_id', None)
        request.session.pop('pending_email_code', None)
        request.session.pop('pending_birth_date', None)
        request.session.pop('pending_birth_city', None)
        request.session.pop('pending_email', None)
        request.session.pop('pending_code_sent_at', None)


    if request.method == 'POST':
        stage = request.POST.get('stage', 'register')
        # Étape 2 : saisie du code
        if stage == 'confirm_code':
            if not awaiting_code:
                messages.error(request, "Aucune inscription en attente. Merci de recommencer.")
                return redirect('register')
            code_saisi = request.POST.get('code', '').strip()
            if code_saisi and code_saisi == pending_code:
                user = User.objects.get(id=pending_user_id)
                _activate_user_and_create_accounts(user)
                login(request, user)
                messages.success(request, "Email confirmé, compte activé. 100€ offerts.")
                return redirect('dashboard')
            else:
                messages.error(request, "Code invalide. Veuillez réessayer.")
                return render(request, 'registration/register.html', {
                    'form': InscriptionForm(),
                    'awaiting_code': True,
                    'pending_email': pending_email
                })

        # Renvoyer un code sans rejouer l'inscription
        if stage == 'resend' and awaiting_code:
            try:
                user = User.objects.get(id=pending_user_id)
                _send_confirmation_code(user)
                messages.info(request, "Un nouveau code a été envoyé.")
            except Exception:
                messages.error(request, "Impossible d'envoyer un nouveau code pour le moment.")
            return render(request, 'registration/register.html', {
                'form': InscriptionForm(),
                'awaiting_code': True,
                'pending_email': pending_email or (user.email if 'user' in locals() else None)
            })

        # Bouton temporaire : activer sans code (bypass)
        if stage == 'skip_code' and awaiting_code:
            try:
                user = User.objects.get(id=pending_user_id)
                _activate_user_and_create_accounts(user)
                login(request, user)
                messages.warning(request, "Activation effectuée sans code (mode temporaire). Pensez à réactiver l'email plus tard.")
                return redirect('dashboard')
            except Exception:
                messages.error(request, "Impossible de passer l'étape pour le moment.")
                return redirect('register')

        # Bloquer une nouvelle inscription tant qu'un code est en attente
        if awaiting_code:
            messages.info(request, "Un code a déjà été envoyé. Saisissez-le ci-dessous pour activer votre compte.")
            return render(request, 'registration/register.html', {
                'form': InscriptionForm(),
                'awaiting_code': True,
                'pending_email': pending_email
            })

        # Étape 1 : création du compte + envoi code
        form = InscriptionForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.is_active = False
            user.save(update_fields=["is_active"])

            request.session['pending_birth_date'] = str(form.cleaned_data.get('birth_date'))
            request.session['pending_birth_city'] = form.cleaned_data.get('birth_city')
            _send_confirmation_code(user)

            messages.info(request, "Nous avons envoyé un code à 6 chiffres sur votre email. Saisissez-le pour activer votre compte.")
            return render(request, 'registration/register.html', {
                'form': form,
                'awaiting_code': True,
                'pending_email': user.email
            })
    else:
        form = InscriptionForm()
    return render(request, 'registration/register.html', {
        'form': form,
        'awaiting_code': awaiting_code,
        'pending_email': pending_email
    })


def _create_default_accounts(user, form):
    profil, _ = ProfilClient.objects.get_or_create(
        user=user,
        defaults={
            'date_de_naissance': form.cleaned_data.get('birth_date'),
            'ville_naissance': form.cleaned_data.get('birth_city'),
            'abonnement': 'ESSENTIEL',
            'prochaine_facturation': timezone.now().date() + timedelta(days=30)
        }
    )
    compte = Compte.objects.create(
        user=user,
        type_compte='COURANT',
        solde=100.00,
        numero_compte=f"FR76{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}",
        est_actif=True
    )
    Carte.objects.create(
        compte=compte,
        numero_visible=str(random.randint(1000,9999)),
        date_expiration=timezone.now()+timedelta(days=365*4),
        est_bloquee=False,
        sans_contact_actif=True,
        paiement_etranger_actif=False
    )
    Transaction.objects.create(
        compte=compte,
        montant=100.00,
        libelle="Cadeau de bienvenue Banquise",
        type='CREDIT',
        categorie='SALAIRE'
    )
    return profil


def confirm_email(request):
    user_id = request.session.get('pending_user_id')
    code_session = request.session.get('pending_email_code')
    code_sent_at_raw = request.session.get('pending_code_sent_at')
    try:
        code_sent_at = timezone.datetime.fromisoformat(code_sent_at_raw) if code_sent_at_raw else None
    except Exception:
        code_sent_at = None
    if not user_id or not code_session:
        messages.error(request, "Aucune inscription en attente. Merci de recommencer.")
        return redirect('register')

    def resend_code():
        code_new = f"{random.randint(100000, 999999)}"
        request.session['pending_email_code'] = code_new
        request.session['pending_code_sent_at'] = timezone.now().isoformat()
        user = User.objects.get(id=user_id)
        try:
            send_mail(
                "Banquise - Nouveau code de confirmation",
                f"Votre nouveau code de vérification est : {code_new}",
                "no-reply@banquise.demo",
                [user.email],
                fail_silently=True
            )
        except Exception:
            pass
        messages.info(request, "Un nouveau code a été envoyé.")

    if request.method == 'POST':
        code_saisi = request.POST.get('code', '').strip()
        if 'resend' in request.POST:
            resend_code()
            return redirect('confirm_email')

        if code_saisi and code_saisi == code_session:
            user = User.objects.get(id=user_id)
            user.is_active = True
            user.save(update_fields=['is_active'])

            birth_date_raw = request.session.get('pending_birth_date') or None
            try:
                birth_date = timezone.datetime.fromisoformat(birth_date_raw).date() if birth_date_raw else None
            except Exception:
                birth_date = None
            birth_city = request.session.get('pending_birth_city') or ""
            # Créer profil + compte si pas déjà fait
            ProfilClient.objects.get_or_create(
                user=user,
                defaults={
                    'date_de_naissance': birth_date,
                    'ville_naissance': birth_city,
                    'abonnement': 'ESSENTIEL',
                    'prochaine_facturation': timezone.now().date() + timedelta(days=30)
                }
            )
            if not Compte.objects.filter(user=user).exists():
                compte = Compte.objects.create(
                    user=user,
                    type_compte='COURANT',
                    solde=100.00,
                    numero_compte=f"FR76{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}",
                    est_actif=True
                )
                Carte.objects.create(
                    compte=compte,
                    numero_visible=str(random.randint(1000,9999)),
                    date_expiration=timezone.now()+timedelta(days=365*4),
                    est_bloquee=False,
                    sans_contact_actif=True,
                    paiement_etranger_actif=False
                )
                Transaction.objects.create(
                    compte=compte,
                    montant=100.00,
                    libelle="Cadeau de bienvenue Banquise",
                    type='CREDIT',
                    categorie='SALAIRE'
                )

            # Nettoyage session
            request.session.pop('pending_user_id', None)
            request.session.pop('pending_email_code', None)
            request.session.pop('pending_birth_date', None)
            request.session.pop('pending_birth_city', None)
            request.session.pop('pending_email', None)
            request.session.pop('pending_code_sent_at', None)

            login(request, user)
            messages.success(request, "Email confirmé, compte activé. 100€ offerts.")
            return redirect('dashboard')
        else:
            messages.error(request, "Code invalide. Veuillez réessayer.")

    # Si le code est trop vieux (>10 minutes), proposer l'envoi
    expired = False
    if code_sent_at and timezone.now() - code_sent_at > timedelta(minutes=10):
        expired = True

    return render(request, 'registration/confirm_email.html', {'expired': expired})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    unread_notifs = 0
    return render(request, 'registration/login.html', {'form': form, 'unread_notifs': unread_notifs})

def logout_view(request):
    logout(request)
    request.session.flush()
    messages.info(request, "Vous êtes déconnecté.")
    resp = redirect('home')
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ==============================================================================
# 2. GESTION DES COMPTES (Dashboard, Ouvrir, Fermer, Relevé, Stats)
# ==============================================================================

@login_required
def dashboard(request):
    comptes = Compte.objects.filter(user=request.user, est_actif=True)
    cartes = Carte.objects.filter(compte__in=comptes)
    transactions = Transaction.objects.filter(compte__in=comptes).order_by('-date_execution')[:5]
    demandes_credit = DemandeCredit.objects.filter(user=request.user).order_by('-date_demande')[:5]
    credits_actifs = DemandeCredit.objects.filter(user=request.user, statut='ACCEPTEE').order_by('date_demande')
    profil, _ = ProfilClient.objects.get_or_create(user=request.user, defaults={
        'abonnement': 'ESSENTIEL',
        'prochaine_facturation': timezone.now().date() + timedelta(days=30)
    })
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()
    overdraft_limit = overdraft_limit_for_user(request.user)
    overdraft_margins = {c.id: overdraft_limit + c.solde for c in comptes}
    for c in comptes:
        c.marge_dispo = overdraft_margins.get(c.id)

    # Prélèvements mensuels automatiques sur crédits acceptés
    if credits_actifs.exists():
        today = timezone.now().date()
        compte_principal = comptes.order_by('id').first()
        if compte_principal:
            for credit in credits_actifs:
                total_months = max(1, (credit.duree_souhaitee_annees or 1) * 12)
                deja_payees = credit.echeances_payees or 0
                start_date = credit.date_demande.date()
                due_months = min(total_months, months_diff(today, start_date) + 1)
                manquantes = max(0, due_months - deja_payees)
                mensualite = credit.mensualite_calculee or Decimal("0")
                for _ in range(manquantes):
                    Transaction.objects.create(
                        compte=compte_principal,
                        montant=-mensualite,
                        libelle="Mensualité crédit",
                        type='DEBIT',
                        categorie='CREDIT'
                    )
                if manquantes > 0:
                    credit.echeances_payees = deja_payees + manquantes
                    credit.dernier_prelevement = today
                    credit.save(update_fields=['echeances_payees', 'dernier_prelevement'])

    # Analyse dépenses (débits) sur les 6 derniers mois
    def month_shift(date_obj, shift):
        year = date_obj.year + (date_obj.month - 1 + shift) // 12
        month = (date_obj.month - 1 + shift) % 12 + 1
        return date_obj.replace(year=year, month=month, day=1)

    today = timezone.now().date()
    start_month = today.replace(day=1)
    def build_spending(n_months):
        lbls, vals = [], []
        for i in range(n_months - 1, -1, -1):
            m_date = month_shift(start_month, -i)
            total = Transaction.objects.filter(
                compte__in=comptes,
                type='DEBIT',
                date_execution__year=m_date.year,
                date_execution__month=m_date.month
            ).aggregate(total=Sum('montant'))['total'] or 0
            lbls.append(m_date.strftime("%b %y"))
            vals.append(abs(float(total)))
        return lbls, vals

    labels_6, values_6 = build_spending(6)
    labels_12, values_12 = build_spending(12)

    credit_labels = []
    credit_datasets = []
    if credits_actifs.exists():
        today = timezone.now().date()
        max_remaining = 0
        credits_info = []
        for idx, cr in enumerate(credits_actifs):
            total_months = max(1, (cr.duree_souhaitee_annees or 1) * 12)
            elapsed = max(0, months_diff(today, cr.date_demande.date()))
            remaining = max(0, total_months - elapsed)
            max_remaining = max(max_remaining, remaining)
            mensualite = cr.mensualite_calculee or Decimal("0")
            credits_info.append((cr, remaining, float(mensualite)))
        horizon = int(min(24, max_remaining))
        for i in range(horizon):
            m_date = month_shift(start_month, i)  # réutilise start_month (courant)
            credit_labels.append(m_date.strftime("%b %y"))
        palette = ["#0ea5e9", "#22c55e", "#f59e0b", "#6366f1", "#ef4444", "#14b8a6"]
        for idx, (cr, remaining, mensu) in enumerate(credits_info):
            data = []
            for m in range(len(credit_labels)):
                data.append(mensu if m < remaining else 0)
            credit_datasets.append({
                "label": f"{cr.produit.nom if cr.produit else 'Crédit'}",
                "data": data,
                "color": palette[idx % len(palette)]
            })

    response = render(request, 'scoring/dashboard.html', {
        'comptes': comptes,
        'cartes': cartes,
        'transactions_recentes': transactions,
        'profil_client': profil,
        'plans': PLAN_CONFIG,
        'unread_notifs': unread_notifs,
        'spending_labels_6': json.dumps(labels_6),
        'spending_values_6': json.dumps(values_6),
        'spending_labels_12': json.dumps(labels_12),
        'spending_values_12': json.dumps(values_12),
        'credit_labels': json.dumps(credit_labels),
        'credit_datasets': json.dumps(credit_datasets),
        'overdraft_limit': overdraft_limit,
        'overdraft_margins': overdraft_margins,
        'demandes_credit_recent': demandes_credit,
    })
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@login_required
def gerer_comptes(request):
    comptes = Compte.objects.filter(user=request.user).prefetch_related('cartes')
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()
    return render(request, 'scoring/gerer_comptes.html', {
        'comptes': comptes,
        'unread_notifs': unread_notifs,
        'overdraft_limit': overdraft_limit_for_user(request.user),
    })

@login_required
@transaction.atomic
def changer_abonnement(request):
    if request.method != 'POST':
        return redirect('dashboard')

    plan = request.POST.get('plan')
    profil, _ = ProfilClient.objects.get_or_create(user=request.user, defaults={
        'abonnement': 'ESSENTIEL',
        'prochaine_facturation': timezone.now().date() + timedelta(days=30)
    })

    if plan == 'RESILIER':
        profil.prochain_abonnement = 'ESSENTIEL'
        profil.save(update_fields=['prochain_abonnement'])
        messages.success(request, "Votre abonnement sera résilié à la fin de la période en cours (retour à Essentiel).")
        return redirect('dashboard')

    if plan not in PLAN_CONFIG:
        messages.error(request, "Formule inconnue.")
        return redirect('dashboard')

    if plan == profil.abonnement:
        messages.info(request, "Vous êtes déjà sur cette formule.")
        return redirect('dashboard')

    compte = Compte.objects.filter(user=request.user, est_actif=True).order_by('id').first()
    if not compte:
        messages.error(request, "Aucun compte actif pour débiter l'abonnement.")
        return redirect('dashboard')

    prix = PLAN_CONFIG[plan]['prix']
    if compte.solde < prix:
        messages.error(request, "Solde insuffisant pour activer cette formule.")
        return redirect('dashboard')

    compte.solde = compte.solde - prix
    compte.save(update_fields=['solde'])
    Transaction.objects.create(
        compte=compte,
        montant=-prix,
        libelle=f"Abonnement Banquise {PLAN_CONFIG[plan]['label']}",
        type='DEBIT',
        categorie='AUTRE'
    )
    notifier(request.user, "Abonnement modifié", f"Passage à {PLAN_CONFIG[plan]['label']} facturé {prix} €.", "TRANSACTION", url=reverse('dashboard'))
    enforce_overdraft(compte)

    profil.abonnement = plan
    profil.prochain_abonnement = plan
    profil.prochaine_facturation = timezone.now().date() + timedelta(days=30)
    profil.save(update_fields=['abonnement', 'prochain_abonnement', 'prochaine_facturation'])

    messages.success(request, f"Formule {PLAN_CONFIG[plan]['label']} activée. Prochaine facturation dans 30 jours.")
    return redirect('dashboard')


@login_required
def demande_decouvert(request):
    if request.method != 'POST':
        return redirect('dashboard')

    try:
        montant = Decimal(request.POST.get('montant', '0'))
    except Exception:
        messages.error(request, "Montant invalide.")
        return redirect('dashboard')

    if montant <= 0:
        messages.error(request, "Le montant doit être supérieur à 0.")
        return redirect('dashboard')

    duree_jours = request.POST.get('duree_jours')
    expire_le = None
    if duree_jours:
        try:
            expire_le = timezone.now().date() + timedelta(days=int(duree_jours))
        except Exception:
            expire_le = None

    DemandeDecouvert.objects.create(
        user=request.user,
        montant_souhaite=montant,
        expire_le=expire_le,
        statut='EN_ATTENTE'
    )
    for admin in User.objects.filter(is_staff=True):
        notifier(admin, "Demande de découvert", f"{request.user.username} demande {montant} € de découvert temporaire.", "INFO", url=reverse('admin_manage'))

    messages.success(request, "Demande de relèvement de découvert envoyée. Un admin doit la valider.")
    return redirect('dashboard')


def page_abonnements(request):
    profil = None
    if request.user.is_authenticated:
        profil, _ = ProfilClient.objects.get_or_create(user=request.user, defaults={
            'abonnement': 'ESSENTIEL',
            'prochaine_facturation': timezone.now().date() + timedelta(days=30)
        })
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count() if request.user.is_authenticated else 0
    return render(request, 'scoring/abonnements.html', {
        'plans': PLAN_CONFIG,
        'profil_client': profil,
        'unread_notifs': unread_notifs
    })


@login_required
def chat_support(request):
    # Récupère l'historique de l'utilisateur
    messages_support = MessageSupport.objects.filter(user=request.user)
    unread_count = Notification.objects.filter(user=request.user, est_lu=False).count()

    if request.method == 'POST':
        action = request.POST.get('action', 'create')
        if action == 'delete':
            msg_id = request.POST.get('message_id')
            msg = get_object_or_404(MessageSupport, id=msg_id, user=request.user)
            msg.delete()
            messages.success(request, "Message supprimé.")
            return redirect('chat_support')
        elif action == 'edit':
            msg_id = request.POST.get('message_id')
            msg = get_object_or_404(MessageSupport, id=msg_id, user=request.user, est_admin=False)
            contenu = (request.POST.get('message') or "").strip()
            if not contenu:
                messages.error(request, "Le message doit contenir du texte.")
            elif contenu == msg.contenu:
                messages.info(request, "Aucun changement détecté.")
            else:
                msg.contenu = contenu
                msg.a_ete_modifie = True
                msg.save()
                messages.success(request, "Message modifié.")
            return redirect('chat_support')
        else:
            contenu = (request.POST.get('message') or "").strip()
            image = request.FILES.get('image')
            if not contenu and not image:
                messages.error(request, "Le message doit contenir du texte ou une image.")
            else:
                MessageSupport.objects.create(
                    user=request.user,
                    contenu=contenu or "",
                    est_admin=False,
                    image=image
                )
                notifier(request.user, "Message envoyé", "Votre message a été envoyé au support.", "INFO", url=reverse('chat_support'))
                # Notify all staff members
                staff_users = User.objects.filter(is_staff=True)
                for admin in staff_users:
                    notifier(admin, "Nouveau message client", f"{request.user.username}: {(contenu or 'Pièce jointe')[:80]}", "INFO", url=f"{reverse('chat_support_admin')}?user={request.user.id}")
                messages.success(request, "Message envoyé au support.")
                return redirect('chat_support')

    return render(request, 'scoring/chat_support.html', {
        'messages_support': messages_support,
        'unread_notifs': unread_count
    })


@staff_member_required
def chat_support_admin(request):
    # Liste des conversations ordonnées par dernier message
    from django.db.models import Max
    filter_user = request.GET.get('user')
    base_threads = MessageSupport.objects.values('user').annotate(last=Max('date_envoi')).order_by('-last')
    conversations = []
    unread_count = Notification.objects.filter(user=request.user, est_lu=False).count()
    selected_convo = None
    for t in base_threads:
        user_obj = User.objects.filter(id=t['user']).first()
        msgs = MessageSupport.objects.filter(user_id=t['user']).order_by('date_envoi')
        last_msg = msgs.last()
        unread = msgs.filter(est_lu=False).exists()
        unseen_last = False
        conversations.append({'user': user_obj, 'messages': msgs})
        if last_msg:
            conversations[-1].update({
                'last_message_preview': (last_msg.contenu or ("Pièce jointe" if last_msg.image else "—")).strip(),
                'last_message_time': last_msg.date_envoi,
                'unread': unread,
                'unseen_last': unseen_last,
            })
    selected_user = filter_user or (conversations[0]['user'].id if conversations else None)
    selected_convo = None
    if selected_user:
        for convo in conversations:
            if str(convo['user'].id) == str(selected_user):
                selected_convo = convo
                break
    # Marquer la conversation sélectionnée comme lue
    if selected_convo and selected_convo.get('messages'):
        msg_ids = [m.id for m in selected_convo['messages'] if not m.est_lu]
        if msg_ids:
            MessageSupport.objects.filter(id__in=msg_ids).update(est_lu=True)
            # Met à jour les objets en mémoire et la pastille dans la liste
            for m in selected_convo['messages']:
                m.est_lu = True
            for conv in conversations:
                if conv['user'].id == selected_convo['user'].id:
                    conv['unseen_last'] = False
                    conv['unread'] = False
        selected_convo['unseen_last'] = False

    # Réponse à un utilisateur ciblé
    if request.method == 'POST':
        action = request.POST.get('action', 'reply')
        if action == 'delete':
            msg_id = request.POST.get('message_id')
            msg = get_object_or_404(MessageSupport, id=msg_id)
            msg.delete()
            messages.success(request, "Message supprimé.")
            return redirect('chat_support_admin')
        elif action == 'edit':
            msg_id = request.POST.get('message_id')
            msg = get_object_or_404(MessageSupport, id=msg_id, est_admin=True)
            contenu = (request.POST.get('message') or "").strip()
            if not contenu:
                messages.error(request, "Le message doit contenir du texte.")
            elif contenu == msg.contenu:
                messages.info(request, "Aucun changement détecté.")
            else:
                msg.contenu = contenu
                msg.a_ete_modifie = True
                msg.save()
                messages.success(request, "Message modifié.")
            return redirect('chat_support_admin')
        else:
            target_user_id = request.POST.get('target_user')
            contenu = (request.POST.get('message') or "").strip()
            image = request.FILES.get('image')
            if target_user_id and (contenu or image):
                MessageSupport.objects.create(
                    user_id=target_user_id,
                    contenu=contenu or "",
                    est_admin=True,
                    image=image
                )
                notifier(User.objects.get(id=target_user_id), "Réponse support", (contenu or "Pièce jointe")[:120], "INFO", url=reverse('chat_support'))
                messages.success(request, "Message envoyé au client.")
                return redirect('chat_support_admin')
            else:
                messages.error(request, "Sélectionnez un utilisateur et saisissez un message ou une image.")

    return render(request, 'scoring/chat_support_admin.html', {
        'conversations': conversations,
        'filter_user': filter_user,
        'unread_notifs': unread_count,
        'selected_convo': selected_convo
    })


@login_required
def notifications_view(request):
    notifs = Notification.objects.filter(user=request.user)
    if request.method == 'POST':
        notifs.update(est_lu=True)
        messages.success(request, "Notifications marquées comme lues.")
        return redirect('notifications')
    unread_count = notifs.filter(est_lu=False).count()
    return render(request, 'scoring/notifications.html', {'notifications': notifs, 'unread_notifs': unread_count})

@login_required
def statistiques(request):
    comptes = Compte.objects.filter(user=request.user)
    today = timezone.now()
    transactions = Transaction.objects.filter(
        compte__in=comptes,
        type='DEBIT',
        date_execution__month=today.month,
        date_execution__year=today.year
    )

    depenses_par_cat = transactions.values('categorie').annotate(total=Sum('montant')).order_by('-total')
    labels = []
    data = []
    cat_dict = dict(Transaction.CATEGORIE_CHOICES)
    
    for item in depenses_par_cat:
        cat_code = item['categorie']
        montant_abs = abs(float(item['total'])) 
        labels.append(cat_dict.get(cat_code, cat_code))
        data.append(montant_abs)

    # Évolution sur 6 mois (débits)
    def month_shift(date_obj, shift):
        year = date_obj.year + (date_obj.month - 1 + shift) // 12
        month = (date_obj.month - 1 + shift) % 12 + 1
        return date_obj.replace(year=year, month=month, day=1)

    start_month = today.date().replace(day=1)
    monthly_labels = []
    monthly_values = []
    for i in range(5, -1, -1):
        m_date = month_shift(start_month, -i)
        total = Transaction.objects.filter(
            compte__in=comptes,
            type='DEBIT',
            date_execution__year=m_date.year,
            date_execution__month=m_date.month
        ).aggregate(total=Sum('montant'))['total'] or 0
        monthly_labels.append(m_date.strftime("%b %y"))
        monthly_values.append(abs(float(total)))

    context = {
        'labels_json': json.dumps(labels),
        'data_json': json.dumps(data),
        'cat_labels': labels,
        'cat_values': data,
        'total_depenses': sum(data),
        'month_name': today.strftime('%B %Y'),
        'monthly_labels_json': json.dumps(monthly_labels),
        'monthly_data_json': json.dumps(monthly_values),
    }
    return render(request, 'scoring/statistiques.html', context)

@login_required
def releve_compte(request, compte_id):
    compte = get_object_or_404(Compte, id=compte_id, user=request.user, est_actif=True)
    transactions_list = Transaction.objects.filter(compte=compte).order_by('-date_execution')
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()
    
    form = TransactionFilterForm(request.GET)
    if form.is_valid():
        if form.cleaned_data['date_debut']:
            transactions_list = transactions_list.filter(date_execution__date__gte=form.cleaned_data['date_debut'])
        if form.cleaned_data['date_fin']:
            transactions_list = transactions_list.filter(date_execution__date__lte=form.cleaned_data['date_fin'])
        if form.cleaned_data['type_transaction']:
            transactions_list = transactions_list.filter(type=form.cleaned_data['type_transaction'])
        if form.cleaned_data.get('categorie'):
             transactions_list = transactions_list.filter(categorie=form.cleaned_data['categorie'])
        if form.cleaned_data['montant_min']:
            transactions_list = transactions_list.filter(montant__gte=form.cleaned_data['montant_min'])
        if form.cleaned_data['montant_max']:
            transactions_list = transactions_list.filter(montant__lte=form.cleaned_data['montant_max'])

    paginator = Paginator(transactions_list, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'scoring/releve_compte.html', {
        'compte': compte,
        'page_obj': page_obj,
        'form': form,
        'has_reportlab': HAS_REPORTLAB,
        'unread_notifs': unread_notifs
    })

# Génération PDF Relevé
@login_required
def telecharger_releve_pdf(request, compte_id):
    if not HAS_REPORTLAB:
        messages.error(request, "La génération de PDF n'est pas disponible (reportlab non installé).")
        return redirect('releve_compte', compte_id=compte_id)

    compte = get_object_or_404(Compte, id=compte_id, user=request.user)
    transactions = Transaction.objects.filter(compte=compte).order_by('-date_execution')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=inch/2, leftMargin=inch/2, topMargin=inch/2, bottomMargin=inch/2)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(f"Relevé de compte - {compte.get_type_compte_display()}", styles['Title']))
    elements.append(Paragraph(f"Période: Depuis le début jusqu'au {timezone.now().strftime('%d/%m/%Y')}", styles['Normal']))
    elements.append(HRFlowable(width="100%", thickness=1, lineCap='round', color=colors.black))
    elements.append(Paragraph(f"Titulaire: {request.user.first_name} {request.user.last_name}", styles['Normal']))
    elements.append(Paragraph(f"IBAN: {compte.numero_compte}", styles['Normal']))
    elements.append(Paragraph(f"BIC: {BANQUISE_BIC}", styles['Normal']))
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Solde au {timezone.now().strftime('%d/%m/%Y')}: <b>{compte.solde} €</b>", styles['Normal']))
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("<b>Détail des Transactions:</b>", styles['Heading3']))

    data = [['Date', 'Libellé', 'Type', 'Catégorie', 'Montant']]
    for t in transactions:
        data.append([
            t.date_execution.strftime("%d/%m/%Y %H:%M"),
            t.libelle[:40],
            t.get_type_display(),
            t.get_categorie_display(),
            f"{t.montant} €"
        ])

    table = Table(data, colWidths=[1.2*inch, 3*inch, 0.8*inch, 1*inch, 1*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F3F4F6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1E293B')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
    ]))
    
    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="releve_compte_{compte.numero_compte}.pdf"'
    return response

# Génération PDF RIB
@login_required
def telecharger_rib_pdf(request, compte_id):
    if not HAS_REPORTLAB:
        messages.error(request, "La génération de PDF n'est pas disponible (reportlab non installé).")
        return redirect('profil')

    compte = get_object_or_404(Compte, id=compte_id, user=request.user)

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=inch, leftMargin=inch, topMargin=inch, bottomMargin=inch)
    elements = []
    styles = getSampleStyleSheet()
    
    style_titre = ParagraphStyle('Titre', parent=styles['Title'], fontSize=20, spaceAfter=20, alignment=1)
    
    elements.append(Paragraph("Relevé d'Identité Bancaire (RIB)", style_titre))
    elements.append(Paragraph("<font size=12><b>BANQUISE</b></font>", styles['Normal']))
    elements.append(Paragraph(f"Titulaire: {request.user.first_name} {request.user.last_name}", styles['Normal']))
    elements.append(HRFlowable(width="100%", thickness=1, lineCap='round', color=colors.HexColor('#0EA5E9'), spaceAfter=20))
    
    rib_data = [
        ["INFORMATION", "DÉTAIL"],
        ["Banque", "Banquise"],
        ["Code BIC / SWIFT", BANQUISE_BIC],
        ["Type de Compte", compte.get_type_compte_display()],
        ["Numéro de Compte / IBAN", compte.numero_compte],
        ["Titulaire du Compte", f"{request.user.first_name} {request.user.last_name}"],
    ]
    
    table = Table(rib_data, colWidths=[2.5*inch, 4*inch])
    table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#F3F4F6')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#F0F9FF')),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 36))
    elements.append(Paragraph("Document à fournir pour recevoir des virements en zone SEPA.", styles['Italic']))

    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rib_banquise_{compte.numero_compte}.pdf"'
    return response


@login_required
def ouvrir_compte(request):
    nb_comptes_actifs = Compte.objects.filter(user=request.user, est_actif=True).count()
    if nb_comptes_actifs >= 3:
        messages.warning(request, "Vous avez atteint la limite maximale de 3 comptes actifs.")
        return redirect('dashboard')

    if request.method == 'POST':
        form = OuvrirCompteForm(request.user, request.POST)
        if form.is_valid():
            type_choisi = form.cleaned_data['type_compte']
            
            # Vérification si le compte existe déjà
            if Compte.objects.filter(user=request.user, est_actif=True, type_compte=type_choisi).exists():
                messages.error(request, f"Vous possédez déjà un compte de type {type_choisi}.")
                return redirect('ouvrir_compte')

            # --- C'est cette ligne qui manquait ou était incorrecte ---
            # Génération de l'IBAN (sans espaces pour compatibilité virements)
            numero = f"FR76{random.randint(1000,9999)}{random.randint(1000,9999)}{random.randint(1000,9999)}"
            
            nouveau_compte = Compte.objects.create(
                user=request.user,
                type_compte=type_choisi,
                solde=0.00,
                numero_compte=numero, # Utilisation de la variable définie juste au-dessus
                est_actif=True
            )
            
            Carte.objects.create(
                compte=nouveau_compte,
                numero_visible=str(random.randint(1000,9999)),
                date_expiration=timezone.now()+timedelta(days=365*4),
                est_bloquee=False,
                sans_contact_actif=True,
                paiement_etranger_actif=False
            )

            messages.success(request, f"Nouveau compte {nouveau_compte.get_type_compte_display()} ouvert et carte commandée !")
            return redirect('dashboard')
    else:
        form = OuvrirCompteForm(request.user)
        # Vérifie s'il reste des types de comptes disponibles à ouvrir
        if not form.fields['type_compte'].choices:
            messages.info(request, "Vous possédez déjà tous les types de comptes disponibles.")
            return redirect('dashboard')
    
    return render(request, 'scoring/open_compte.html', {'form': form})

@login_required
def fermer_compte(request, compte_id):
    compte = get_object_or_404(Compte, id=compte_id, user=request.user, est_actif=True)
    if request.method == 'POST':
        form = CloturerCompteForm(request.user, compte, request.POST)
        if form.is_valid():
            password = form.cleaned_data['password']
            destination = form.cleaned_data['compte_destination']
            
            if not request.user.check_password(password):
                messages.error(request, "Mot de passe incorrect.")
                return redirect('fermer_compte', compte_id=compte.id)
            
            if compte.solde > 0:
                if not destination:
                    messages.error(request, "Veuillez choisir un compte pour transférer l'argent restant.")
                    return redirect('fermer_compte', compte_id=compte.id)
                
                with transaction.atomic():
                    montant = compte.solde
                    destination.solde += montant
                    compte.solde = 0
                    destination.save()
                    compte.save()
                    Transaction.objects.create(
                        compte=destination, 
                        montant=montant, 
                        libelle=f"Clôture {compte.numero_compte}", 
                        type='CREDIT',
                        categorie='AUTRE'
                    )

            elif compte.solde < 0:
                 messages.error(request, "Impossible de fermer un compte débiteur.")
                 return redirect('dashboard')

            compte.est_actif = False
            compte.save()
            messages.success(request, "Compte clôturé.")
            return redirect('dashboard')
    else:
        form = CloturerCompteForm(request.user, compte)
    return render(request, 'scoring/fermer_compte.html', {'form': form, 'compte': compte})


# ==============================================================================
# 3. CARTES, VIREMENTS ET BENEFICIAIRES
# ==============================================================================

@login_required
def cartes(request):
    comptes = Compte.objects.filter(user=request.user, est_actif=True)
    cartes_list = Carte.objects.filter(compte__in=comptes)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        carte_id = request.POST.get('carte_id')
        carte = get_object_or_404(Carte, id=carte_id, compte__user=request.user)
        
        if action == 'toggle_lock':
            carte.est_bloquee = not carte.est_bloquee
            msg = "verrouillée" if carte.est_bloquee else "déverrouillée"
            messages.success(request, f"Carte {msg}.")
        elif action == 'toggle_contactless':
            carte.sans_contact_actif = not carte.sans_contact_actif
            msg = "activé" if carte.sans_contact_actif else "désactivé"
            messages.success(request, f"Sans contact {msg}.")
        elif action == 'toggle_foreign':
            carte.paiement_etranger_actif = not carte.paiement_etranger_actif
            msg = "autorisé" if carte.paiement_etranger_actif else "bloqué"
            messages.success(request, f"Paiement étranger {msg}.")
            
        carte.save()
        return redirect('cartes')
    return render(request, 'scoring/cartes.html', {'cartes': cartes_list})

@login_required
def gestion_plafonds(request, carte_id):
    carte = get_object_or_404(Carte, id=carte_id, compte__user=request.user, compte__est_actif=True)
    if request.method == 'POST':
        carte.plafond_paiement = request.POST.get('plafond_paiement')
        carte.plafond_retrait = request.POST.get('plafond_retrait')
        carte.save()
        messages.success(request, "Plafonds mis à jour.")
        return redirect('cartes')
    return render(request, 'scoring/plafond.html', {'carte': carte})

@login_required
def virement(request):
    comptes = Compte.objects.filter(user=request.user, est_actif=True)
    
    if request.method == 'POST':
        form = VirementForm(request.user, request.POST)
        if form.is_valid():
            compte = form.cleaned_data['compte_emetteur']
            montant = form.cleaned_data['montant']
            motif = form.cleaned_data['motif']
            
            beneficiaire = form.cleaned_data['beneficiaire_enregistre']
            nouvel_iban = form.cleaned_data['nouveau_beneficiaire_iban']
            
            destinataire_str = ""
            if beneficiaire:
                destinataire_str = f"{beneficiaire.nom} ({beneficiaire.iban})"
            elif nouvel_iban:
                destinataire_str = f"IBAN {nouvel_iban}" 

            if compte.solde >= montant:
                with transaction.atomic():
                    # 1. Débiter l'émetteur
                    compte.solde -= montant
                    compte.save()
                    Transaction.objects.create(
                        compte=compte,
                        montant=-montant,
                        libelle=f"Virement vers {destinataire_str} - {motif}",
                        type='DEBIT',
                        categorie='VIREMENT' 
                    )
                    notifier(request.user, "Virement envoyé", f"Virement vers {destinataire_str} de {montant} €", "VIREMENT", url=reverse('dashboard'))
                    enforce_overdraft(compte)

                    # 2. Créditer le destinataire (si c'est un compte interne)
                    iban_cible = beneficiaire.iban if beneficiaire else nouvel_iban
                    iban_cible_norm = normalize_iban(iban_cible)

                    compte_destinataire = find_account_by_iban(iban_cible_norm)
                    if compte_destinataire:
                        compte_destinataire.solde += montant
                        compte_destinataire.save()

                        Transaction.objects.create(
                            compte=compte_destinataire,
                            montant=montant,
                            libelle=f"Virement reçu de {request.user.first_name} {request.user.last_name} - {motif}",
                            type='CREDIT',
                            categorie='VIREMENT'
                        )
                        notifier(compte_destinataire.user, "Virement reçu", f"Vous avez reçu {montant} € de {request.user.get_full_name()}", "VIREMENT", url=reverse('dashboard'))
                        enforce_overdraft(compte_destinataire)

                messages.success(request, "Virement envoyé avec succès !")
                return redirect('dashboard')
            else:
                messages.error(request, "Solde insuffisant pour effectuer ce virement.")
        return render(request, 'scoring/virement.html', {'form': form, 'comptes': comptes})
    
    else:
        initial_data = {}
        beneficiaire_id = request.GET.get('beneficiaire')
        if beneficiaire_id:
            try:
                bene = Beneficiaire.objects.get(id=beneficiaire_id, user=request.user)
                initial_data['beneficiaire_enregistre'] = bene
            except Beneficiaire.DoesNotExist:
                messages.warning(request, "Bénéficiaire non trouvé.")
                
        form = VirementForm(request.user, initial=initial_data)
        
    return render(request, 'scoring/virement.html', {'form': form, 'comptes': comptes})

@login_required
def gestion_beneficiaires(request):
    beneficiaires_list = Beneficiaire.objects.filter(user=request.user).order_by('-date_ajout')
    return render(request, 'scoring/beneficiaires.html', {'beneficiaires': beneficiaires_list})

@login_required
def ajouter_beneficiaire(request):
    if request.method == 'POST':
        form = BeneficiaireForm(request.POST)
        if form.is_valid():
            bene = form.save(commit=False)
            bene.user = request.user
            bene.save()
            messages.success(request, f"Bénéficiaire '{bene.nom}' ajouté avec succès.")
            return redirect('beneficiaires')
        return render(request, 'scoring/ajouter_beneficiaire.html', {'form': form})
    else:
        form = BeneficiaireForm()
    return render(request, 'scoring/ajouter_beneficiaire.html', {'form': form})

@login_required
def modifier_beneficiaire(request, beneficiaire_id):
    bene = get_object_or_404(Beneficiaire, id=beneficiaire_id, user=request.user)
    if request.method == 'POST':
        form = BeneficiaireForm(request.POST, instance=bene)
        if form.is_valid():
            form.save()
            messages.success(request, f"Bénéficiaire '{bene.nom}' mis à jour.")
            return redirect('beneficiaires')
    else:
        form = BeneficiaireForm(instance=bene)
    return render(request, 'scoring/ajouter_beneficiaire.html', {'form': form, 'edit_mode': True, 'beneficiaire': bene})

@login_required
def supprimer_beneficiaire(request, beneficiaire_id):
    bene = get_object_or_404(Beneficiaire, id=beneficiaire_id, user=request.user)
    if request.method == 'POST':
        bene.delete()
        messages.success(request, f"Bénéficiaire '{bene.nom}' supprimé.")
        return redirect('beneficiaires')
    return render(request, 'scoring/confirmer_suppression_beneficiaire.html', {'beneficiaire': bene})


# ==============================================================================
# 4. CREDITS & SIMULATIONS
# ==============================================================================

@login_required
def page_simulation(request):
    accepted_count = DemandeCredit.objects.filter(user=request.user, statut='ACCEPTEE').count()
    if request.method == 'POST':
        form = SimulationPretForm(request.POST)
        # forcer un minimum sur "Autres crédits en cours"
        if 'dettes_mensuelles' in form.fields:
            form.fields['dettes_mensuelles'].min_value = accepted_count
            form.fields['dettes_mensuelles'].widget.attrs['min'] = accepted_count
        if form.is_valid():
            soumettre = bool(form.cleaned_data.get('soumise'))
            demande = form.save(commit=False)
            demande.user = request.user
            # Valeurs par défaut pour éviter les None / chaînes vides
            demande.dettes_mensuelles = demande.dettes_mensuelles or 0
            demande.loyer_actuel = demande.loyer_actuel or 0
            demande.revenus_mensuels = demande.revenus_mensuels or 0
            demande.apport_personnel = demande.apport_personnel or 0
            demande.montant_souhaite = demande.montant_souhaite or 0
            demande.duree_souhaitee_annees = demande.duree_souhaitee_annees or 1
            
            # --- Simulation robuste ---
            base_rate = demande.produit.taux_ref if demande.produit else Decimal("3.50")
            nb_mois = max(1, (demande.duree_souhaitee_annees or 0) * 12)
            taux_mensuel = (Decimal(base_rate) / Decimal("100")) / Decimal("12")

            if taux_mensuel > 0:
                mensualite = Decimal(demande.montant_souhaite) * taux_mensuel / (1 - (1 + taux_mensuel) ** (-nb_mois))
            else:
                mensualite = Decimal(demande.montant_souhaite) / nb_mois

            dettes_totales = Decimal(demande.dettes_mensuelles or 0) + Decimal(demande.loyer_actuel or 0)
            revenus = Decimal(demande.revenus_mensuels or 1)
            dti = ((mensualite + dettes_totales) / revenus) * Decimal("100")
            ltv = Decimal("100") * (Decimal("1") - (Decimal(demande.apport_personnel or 0) / Decimal(max(1, demande.montant_souhaite or 1))))

            # Heuristique (fallback si modèle ML indisponible)
            heur_score = Decimal("100")
            if dti > Decimal("30"):
                heur_score -= (dti - Decimal("30")) * Decimal("1.0")
            if ltv > Decimal("85"):
                heur_score -= (ltv - Decimal("85")) * Decimal("0.25")
            if revenus < Decimal("2000"):
                heur_score -= Decimal("8")
            if Decimal(demande.apport_personnel or 0) >= Decimal(demande.montant_souhaite or 0) * Decimal("0.2"):
                heur_score += Decimal("10")
            if demande.sante_snapshot == 'BON':
                heur_score += Decimal("2")
            if demande.emploi_snapshot and demande.emploi_snapshot.nom.lower().startswith('cdi'):
                heur_score += Decimal("10")
            if demande.logement_snapshot and 'propri' in (demande.logement_snapshot.nom or '').lower():
                heur_score += Decimal("10")
            heur_score = int(max(0, min(100, heur_score)))

            # Préparation des features pour le modèle ML entraîné offline
            def _build_ml_payload():
                profil = getattr(request.user, "profil", None)
                age_val = None
                try:
                    if profil and profil.date_de_naissance:
                        today = timezone.now().date()
                        age_val = (today - profil.date_de_naissance).days // 365
                except Exception:
                    age_val = None

                dettes_totales_num = float(dettes_totales or 0)
                revenus_num = float(revenus or 0)
                debt_ratio = dettes_totales_num / revenus_num if revenus_num > 0 else None
                rev_util = dettes_totales_num / revenus_num if revenus_num > 0 else None
                dependants = int(demande.enfants_a_charge or 0)
                # Tentative d'alignement sur GiveMeSomeCredit
                return {
                    "RevolvingUtilizationOfUnsecuredLines": rev_util,
                    "age": age_val,
                    "NumberOfTime30-59DaysPastDueNotWorse": 0,
                    "DebtRatio": debt_ratio,
                    "MonthlyIncome": revenus_num or None,
                    "NumberOfOpenCreditLinesAndLoans": DemandeCredit.objects.filter(user=request.user, statut='ACCEPTEE').count() or 0,
                    "NumberOfTimes90DaysLate": 0,
                    "NumberRealEstateLoansOrLines": 1 if demande.logement_snapshot and 'propri' in (demande.logement_snapshot.nom or '').lower() else 0,
                    "NumberOfTime60-89DaysPastDueNotWorse": 0,
                    "NumberOfDependents": dependants,
                }

            ml_result = None
            if is_model_available():
                try:
                    ml_result = predict_credit(_build_ml_payload())
                except ModelNotLoaded:
                    ml_result = None
                except Exception:
                    ml_result = None

            final_score = ml_result["score_0_100"] if ml_result else heur_score
            ia_decision = ml_result["label"] if ml_result else ('ACCEPTEE' if final_score >= 55 else 'REFUSEE')

            # Seuils dynamiques (affichage)
            dti_limit = 42 if demande.revenus_mensuels < 6000 else 47
            ltv_limit = 95
            if demande.montant_souhaite and demande.montant_souhaite >= Decimal("250000") and demande.apport_personnel >= demande.montant_souhaite * Decimal("0.10"):
                ltv_limit = 97

            recommendation = (
                f"Avis automatique {ia_decision.lower()} "
                f"(score final {final_score}, dti {dti:.1f}% / seuil {dti_limit}%, ltv {ltv:.1f}% / seuil {ltv_limit}%)"
            )

            surcharge_risque = Decimal(max(0, (70 - final_score)) * 0.02).quantize(Decimal("0.01"))
            taux_final = Decimal(base_rate) + surcharge_risque

            demande.score_calcule = final_score
            demande.taux_calcule = taux_final
            demande.mensualite_calculee = Decimal(str(mensualite)).quantize(Decimal("0.01"))
            demande.ia_decision = ia_decision
            demande.recommendation = recommendation
            # Toujours validation admin finale
            demande.statut = 'EN_ATTENTE'
            demande.soumise = soumettre
            
            demande.save()
            if soumettre:
                messages.success(request, "Simulation envoyée aux conseillers.")
                notifier(request.user, "Demande de crédit envoyée", f"Avis automatique : {demande.ia_decision or 'En attente'}. Un conseiller va répondre.", "CREDIT", url=reverse('historique'))
                for admin in User.objects.filter(is_staff=True):
                    notifier(admin, "Nouvelle demande de crédit", f"{request.user.username} a validé sa simulation ({demande.montant_souhaite} €).", "CREDIT", url=reverse('admin_manage_credits'))
            return redirect('resultat_simulation', demande_id=demande.id)
    else:
        initial = {}
        # Pré-remplissage depuis la simulation précédente
        mappings = {
            'montant': 'montant_souhaite',
            'duree': 'duree_souhaitee_annees',
            'apport': 'apport_personnel',
            'revenus': 'revenus_mensuels',
            'loyer': 'loyer_actuel',
            'dettes': 'dettes_mensuelles',
            'enfants': 'enfants_a_charge',
            'produit': 'produit',
            'emploi': 'emploi_snapshot',
            'logement': 'logement_snapshot',
            'sante': 'sante_snapshot',
        }
        for param, field in mappings.items():
            val = request.GET.get(param)
            if val:
                # Cast numeric ids and int fields
                if field in ['produit', 'emploi_snapshot', 'logement_snapshot']:
                    try:
                        initial[field] = int(val)
                    except Exception:
                        pass
                elif field == 'sante_snapshot':
                    initial[field] = val
                else:
                    try:
                        initial[field] = int(float(val))
                    except Exception:
                        pass
        form = SimulationPretForm(initial=initial)
        if 'dettes_mensuelles' in form.fields:
            form.fields['dettes_mensuelles'].min_value = accepted_count
            form.fields['dettes_mensuelles'].widget.attrs['min'] = accepted_count
            if not request.GET.get('dettes'):
                form.initial['dettes_mensuelles'] = accepted_count
    return render(request, 'scoring/saisie_client.html', {
        'form': form,
        'from_suggestion': request.GET.get('from_suggestion') == '1'
    })

@login_required
def page_resultat(request, demande_id):
    demande = get_object_or_404(DemandeCredit, id=demande_id, user=request.user)
    mensualite_max = int(demande.revenus_mensuels * 0.35)
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()
    score_val = demande.score_calcule or 0
    gauge_offset = max(0, 440 - (score_val * 4.4))

    # Suggestion durée/mensualité si DTI trop élevé (ou avis refusé)
    suggested_mensualite = None
    suggested_duree = None
    revenus = Decimal(demande.revenus_mensuels or 0)
    dettes_totales = Decimal(demande.dettes_mensuelles or 0) + Decimal(demande.loyer_actuel or 0)
    mensualite_actuelle = Decimal(demande.mensualite_calculee or 0)
    principal = Decimal(demande.montant_souhaite or 0)
    taux = Decimal(demande.taux_calcule or (demande.produit.taux_ref if demande.produit else Decimal("3.50")) or 0)
    r = (taux / Decimal("100")) / Decimal("12")
    cible = (revenus * Decimal("0.35")) - dettes_totales

    # Cas où la mensualité dépasse le DTI cible
    if cible > 0 and mensualite_actuelle and mensualite_actuelle > cible:
        try:
            suggested_mensualite = int(max(Decimal("50"), cible))
            months = None
            if r > 0 and suggested_mensualite > 0 and (r * principal) < (Decimal(suggested_mensualite) * Decimal("0.99")):
                months = -log(1 - (r * principal / Decimal(suggested_mensualite))) / log(1 + r)
            if months is None or months <= 0:
                months = principal / Decimal(suggested_mensualite) if suggested_mensualite > 0 else 0
            if months and months > 0:
                suggested_duree = max(1, min(40, int(ceil(months / 12))))
        except Exception:
            suggested_mensualite = None
            suggested_duree = None

    # Fallback si refus : proposer toujours une durée/mensualité cible DTI 35 %
    if (suggested_mensualite is None or suggested_duree is None) and demande.ia_decision == 'REFUSEE':
        try:
            fallback_target = max(cible, Decimal("50"))
            suggested_mensualite = int(fallback_target.to_integral_value(rounding=ROUND_HALF_UP))
            months = principal / Decimal(suggested_mensualite) if suggested_mensualite > 0 else 12
            suggested_duree = max(1, min(40, int(ceil(months / 12))))
        except Exception:
            suggested_mensualite = suggested_mensualite or None
            suggested_duree = suggested_duree or None
    return render(request, 'scoring/resultat.html', {
        'demande': demande,
        'montant_propose_formate': f"{demande.montant_souhaite:,.0f}".replace(',', ' '),
        'mensualite_max_possible': mensualite_max,
        'unread_notifs': unread_notifs,
        'gauge_offset': gauge_offset,
        'suggested_mensualite': suggested_mensualite,
        'suggested_duree': suggested_duree,
    })


@login_required
def api_update_resultat(request, demande_id):
    demande = get_object_or_404(DemandeCredit, id=demande_id)
    if demande.user != request.user and not request.user.is_staff:
        return JsonResponse({'error': 'forbidden'}, status=403)
    if demande.statut == 'ACCEPTEE':
        return JsonResponse({'error': 'locked'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'error': 'method_not_allowed'}, status=405)
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        payload = request.POST

    try:
        duree = int(payload.get('duree', demande.duree_souhaitee_annees or 1))
    except Exception:
        duree = demande.duree_souhaitee_annees or 1
    try:
        mensualite = Decimal(str(payload.get('mensualite', demande.mensualite_calculee or 0)))
    except Exception:
        mensualite = Decimal(demande.mensualite_calculee or 0)

    taux_ref = demande.taux_calcule or (demande.produit.taux_ref if demande.produit else Decimal("3.50"))
    n = max(1, duree * 12)
    r = Decimal(taux_ref) / Decimal("100") / Decimal("12")
    if r > 0:
        principal = mensualite * (1 - (1 + r) ** (-n)) / r
    else:
        principal = mensualite * n

    demande.duree_souhaitee_annees = duree
    demande.mensualite_calculee = mensualite
    demande.montant_souhaite = principal.quantize(Decimal("0.01"))
    demande.recommendation = f"Simulation ajustée ({duree} ans, {mensualite} €/mois)."
    demande.save(update_fields=['duree_souhaitee_annees', 'mensualite_calculee', 'montant_souhaite', 'recommendation'])

    return JsonResponse({
        'principal': float(principal),
        'duree': duree,
        'mensualite': float(mensualite),
        'taux': float(taux_ref),
    })


@login_required
def valider_demande_credit(request, demande_id):
    demande = get_object_or_404(DemandeCredit, id=demande_id, user=request.user)
    if request.method != 'POST':
        return redirect('resultat_simulation', demande_id=demande.id)
    if demande.soumise:
        messages.info(request, "Cette demande a déjà été envoyée.")
        return redirect('resultat_simulation', demande_id=demande.id)

    demande.soumise = True
    demande.statut = 'EN_ATTENTE'
    demande.save(update_fields=['soumise', 'statut'])
    notifier(request.user, "Demande de crédit envoyée", f"Avis automatique : {demande.ia_decision or 'En attente'}. Un conseiller va répondre.", "CREDIT", url=reverse('historique'))
    for admin in User.objects.filter(is_staff=True):
        notifier(admin, "Nouvelle demande de crédit", f"{request.user.username} a validé sa simulation ({demande.montant_souhaite} €).", "CREDIT", url=reverse('admin_manage_credits'))
    messages.success(request, "Demande envoyée aux conseillers.")
    return redirect('resultat_simulation', demande_id=demande.id)


@staff_member_required
def demande_credit_detail(request, demande_id):
    demande = get_object_or_404(DemandeCredit, id=demande_id)
    comptes = Compte.objects.filter(user=demande.user)
    profil = getattr(demande.user, 'profil', None)
    transactions = Transaction.objects.filter(compte__in=comptes).order_by('-date_execution')[:5]
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()
    total_solde = comptes.aggregate(total=Sum('solde'))['total'] or 0
    return render(request, 'scoring/demande_detail.html', {
        'demande': demande,
        'borrower': demande.user,
        'comptes': comptes,
        'profil': profil,
        'total_solde': total_solde,
        'transactions': transactions,
        'unread_notifs': unread_notifs
    })

@login_required
def page_historique(request):
    demandes = DemandeCredit.objects.filter(user=request.user).order_by('-date_demande')
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()
    return render(request, 'scoring/historique.html', {'demandes': demandes, 'unread_notifs': unread_notifs})

@login_required
def api_calcul_pret_dynamique(request): 
    return JsonResponse({'total_projet_formate': "---"})

@login_required
def supprimer_demande_credit(request, demande_id):
    demande = get_object_or_404(DemandeCredit, id=demande_id, user=request.user)
    if request.method == 'POST':
        username = request.user.username
        demande.delete()
        # Nettoyage des notifications liées au crédit
        Notification.objects.filter(user=request.user, type='CREDIT').delete()
        Notification.objects.filter(type='CREDIT', user__is_staff=True, contenu__icontains=username).delete()
        messages.success(request, "Demande supprimée.")
        return redirect('historique')
    return redirect('historique')

@staff_member_required
def admin_stats_api(request): 
    total_users = User.objects.count()
    total_balance = Compte.objects.filter(est_actif=True).aggregate(total_sum=Sum('solde'))['total_sum'] or 0.00
    pending_loans = DemandeCredit.objects.filter(statut='EN_ATTENTE').count()
    active_accounts = Compte.objects.filter(est_actif=True).count()
    return JsonResponse({
        'status': 'ok',
        'total_users': total_users,
        'total_balance': float(total_balance),
        'pending_loans': pending_loans,
        'active_accounts': active_accounts
    })

@staff_member_required
def admin_validation_credits(request):
    """
    Alias de compatibilité : redirige vers la nouvelle interface de gestion des crédits.
    """
    return redirect('admin_manage_credits')


@staff_member_required
def admin_manage_credits(request):
    demandes = DemandeCredit.objects.select_related('user', 'produit').order_by('-date_demande')
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()

    if request.method == 'POST':
        demande_id = request.POST.get('demande_id')
        action = request.POST.get('action')
        demande = get_object_or_404(DemandeCredit, id=demande_id)

        if action == 'ACCEPTEE':
            if demande.statut != 'ACCEPTEE':
                compte_credit = Compte.objects.filter(user=demande.user, est_actif=True).order_by('id').first()
                if compte_credit:
                    montant = Decimal(demande.montant_souhaite or 0)
                    compte_credit.solde = (compte_credit.solde or 0) + montant
                    compte_credit.save(update_fields=['solde'])
                    Transaction.objects.create(
                        compte=compte_credit,
                        montant=montant,
                        libelle="Versement crédit accepté",
                        type='CREDIT',
                        categorie='CREDIT'
                    )
                else:
                    messages.warning(request, "Aucun compte actif pour créditer le montant.")
            demande.statut = 'ACCEPTEE'
            demande.save(update_fields=['statut'])
            notifier(demande.user, "Crédit accepté", "Votre demande de crédit a été acceptée par un conseillé.", "CREDIT", url=reverse('historique'))
            messages.success(request, "Demande acceptée et montant crédité.")

        elif action == 'REFUSEE':
            demande.statut = 'REFUSEE'
            demande.save(update_fields=['statut'])
            notifier(demande.user, "Crédit refusé", "Votre demande de crédit a été refusée / annulée par un conseillé.", "CREDIT", url=reverse('historique'))
            messages.info(request, "Demande refusée / annulée.")

        return redirect('admin_manage_credits')

    return render(request, 'scoring/admin_credits_manage.html', {
        'demandes': demandes,
        'unread_notifs': unread_notifs,
    })

@staff_member_required
def admin_edit_credit(request, demande_id):
    demande = get_object_or_404(DemandeCredit, id=demande_id)
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()

    if request.method == 'POST':
        montant = request.POST.get('montant_souhaite')
        duree = request.POST.get('duree_souhaitee_annees')
        # mensualite non éditable ici

        if montant:
            demande.montant_souhaite = montant
        if duree:
            demande.duree_souhaitee_annees = duree
        demande.save(update_fields=['montant_souhaite', 'duree_souhaitee_annees'])
        messages.success(request, "Crédit mis à jour.")
        return redirect('admin_manage_credits')

    return render(request, 'scoring/admin_credit_edit.html', {
        'demande': demande,
        'unread_notifs': unread_notifs,
    })


@staff_member_required
def admin_manage(request):
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()

    if request.method == 'POST':
        action = request.POST.get('action')
        target_id = request.POST.get('target_id')
        try:
            if action == 'close_account':
                compte = get_object_or_404(Compte, id=target_id)
                compte.est_actif = False
                compte.save(update_fields=['est_actif'])
                notifier(compte.user, "Compte clôturé", f"Votre compte {compte.numero_compte} a été clôturé par un administrateur.", "INFO")
                messages.success(request, "Compte clôturé.")
            elif action == 'toggle_card':
                carte = get_object_or_404(Carte, id=target_id)
                carte.est_bloquee = not carte.est_bloquee
                carte.save(update_fields=['est_bloquee'])
                notifier(carte.compte.user, "Statut carte", f"Votre carte **** {carte.numero_visible} est désormais {'bloquée' if carte.est_bloquee else 'active'}.", "INFO")
                messages.success(request, "Statut carte mis à jour.")
            elif action == 'delete_beneficiaire':
                bene = get_object_or_404(Beneficiaire, id=target_id)
                bene.delete()
                messages.success(request, "Bénéficiaire supprimé.")
            elif action == 'bulk_block_cards':
                ids = request.POST.get('card_ids', '')
                id_list = [i for i in ids.split(',') if i]
                updated = Carte.objects.filter(id__in=id_list, est_bloquee=False).update(est_bloquee=True)
                messages.success(request, f"{updated} carte(s) bloquée(s).")
            elif action in ['approve_decouvert', 'reject_decouvert']:
                demande = get_object_or_404(DemandeDecouvert, id=target_id)
                if action == 'approve_decouvert':
                    demande.statut = 'ACCEPTEE'
                    commentaire = request.POST.get('commentaire', '')
                    demande.commentaire_admin = commentaire
                    # Optionnel : durée transmise
                    expire = request.POST.get('expire_le')
                    if expire:
                        try:
                            demande.expire_le = datetime.strptime(expire, "%Y-%m-%d").date()
                        except Exception:
                            pass
                    demande.save()
                    notifier(demande.user, "Découvert approuvé", f"Votre découvert temporaire ({demande.montant_souhaite} €) est accepté.", "INFO", url=reverse('dashboard'))
                    messages.success(request, "Demande de découvert acceptée.")
                else:
                    demande.statut = 'REFUSEE'
                    demande.commentaire_admin = request.POST.get('commentaire', '')
                    demande.save(update_fields=['statut', 'commentaire_admin'])
                    notifier(demande.user, "Découvert refusé", "Votre demande de découvert temporaire a été refusée.", "INFO", url=reverse('dashboard'))
                    messages.info(request, "Demande de découvert refusée.")
            else:
                messages.error(request, "Action inconnue.")
        except Exception as e:
            messages.error(request, f"Erreur lors du traitement : {e}")
        return redirect('admin_manage')

    # Filtres
    search = request.GET.get('q', '')
    type_compte = request.GET.get('type_compte')
    card_status = request.GET.get('card_status')

    users = User.objects.all().order_by('-date_joined')[:50]
    comptes_qs = Compte.objects.select_related('user').order_by('-date_creation')
    cartes_qs = Carte.objects.select_related('compte', 'compte__user').order_by('-id')

    if search:
        comptes_qs = comptes_qs.filter(models.Q(user__username__icontains=search) | models.Q(numero_compte__icontains=search))
        cartes_qs = cartes_qs.filter(models.Q(compte__user__username__icontains=search) | models.Q(compte__numero_compte__icontains=search))
    if type_compte:
        comptes_qs = comptes_qs.filter(type_compte=type_compte)
    if card_status == 'active':
        cartes_qs = cartes_qs.filter(est_bloquee=False)
    elif card_status == 'bloquee':
        cartes_qs = cartes_qs.filter(est_bloquee=True)

    comptes = comptes_qs[:100]
    cartes = cartes_qs[:100]
    transactions = Transaction.objects.select_related('compte', 'compte__user').order_by('-date_execution')[:30]
    beneficiaries = Beneficiaire.objects.select_related('user').order_by('-date_ajout')[:50]
    credits = DemandeCredit.objects.select_related('user', 'produit').order_by('-date_demande')[:30]
    demandes_decouvert = DemandeDecouvert.objects.select_related('user').order_by('-cree_le')[:30]

    # Export CSV
    export = request.GET.get('export')
    if export:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{export}.csv"'
        writer = csv.writer(response)
        if export == 'comptes':
            writer.writerow(['Client', 'Type', 'IBAN', 'Solde', 'Actif'])
            for c in comptes_qs:
                writer.writerow([c.user.username, c.get_type_compte_display(), c.numero_compte, c.solde, c.est_actif])
        elif export == 'cartes':
            writer.writerow(['Client', 'Compte', '4 derniers', 'Exp', 'Bloquée'])
            for card in cartes_qs:
                writer.writerow([card.compte.user.username, card.compte.numero_compte, card.numero_visible, card.date_expiration, card.est_bloquee])
        elif export == 'credits':
            writer.writerow(['Client', 'Produit', 'Montant', 'Durée (ans)', 'Statut', 'Score'])
            for d in credits:
                writer.writerow([d.user.username, d.produit.nom if d.produit else '', d.montant_souhaite, d.duree_souhaitee_annees, d.statut, d.score_calcule])
        return response

    # Comptes à risque de découvert
    risque_decouvert = []
    for c in comptes_qs:
        limit = overdraft_limit_for_user(c.user)
        if c.solde < -limit:
            risque_decouvert.append({'compte': c, 'solde': c.solde, 'limite': limit})

    return render(request, 'scoring/admin_manage.html', {
        'users': users,
        'comptes': comptes,
        'cartes': cartes,
        'transactions': transactions,
        'beneficiaires': beneficiaries,
        'unread_notifs': unread_notifs,
        'credits': credits,
        'demandes_decouvert': demandes_decouvert,
        'risque_decouvert': risque_decouvert,
        'search': search,
        'type_compte': type_compte or '',
        'card_status': card_status or '',
    })


@staff_member_required
def admin_reports(request):
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()

    comptes_qs = Compte.objects.select_related('user').all()
    comptes_surveiller = []
    for c in comptes_qs:
        limit = overdraft_limit_for_user(c.user)
        if c.solde < -limit or c.solde < Decimal("50.00"):
            comptes_surveiller.append({'compte': c, 'limite': limit})

    prelevements_retours = Transaction.objects.filter(
        libelle__icontains="prélèvement",
        type='CREDIT'
    ).order_by('-date_execution')[:20]

    # Heatmap dépenses par catégorie sur 6 mois
    today = timezone.now().date()
    months = []
    heatmap_grid = {}
    categories = [c[0] for c in Transaction.CATEGORIE_CHOICES]
    data = {}
    for i in range(5, -1, -1):
        m_date = today.replace(day=1) - timedelta(days=30 * i)
        label = m_date.strftime("%b %y")
        months.append(label)
        for cat in categories:
            key = (label, cat)
            total = Transaction.objects.filter(
                type='DEBIT',
                categorie=cat,
                date_execution__year=m_date.year,
                date_execution__month=m_date.month
            ).aggregate(total=Sum('montant'))['total'] or 0
            data[key] = abs(float(total))
            heatmap_grid.setdefault(cat, {})[label] = abs(float(total))
    max_val = max(data.values()) if data else 1

    return render(request, 'scoring/admin_reports.html', {
        'unread_notifs': unread_notifs,
        'comptes_surveiller': comptes_surveiller,
        'prelevements_retours': prelevements_retours,
        'months': months,
        'categories': categories,
        'heatmap': heatmap_grid,
        'max_val': max_val,
    })


def support(request):
    messages_support = []
    if request.user.is_authenticated:
        messages_support = MessageSupport.objects.filter(user=request.user)

    if request.method == 'POST' and request.user.is_authenticated:
        # Avis (témoignage)
        if 'avis' in request.POST:
            contenu = request.POST.get('avis', '').strip()
            note = request.POST.get('note') or '5'
            if contenu:
                MessageSupport.objects.create(
                    user=request.user,
                    contenu=f"[AVIS][{note}/5] {contenu}",
                    est_admin=False
                )
                messages.success(request, "Merci pour votre avis ! Il sera affiché après validation.")
            else:
                messages.error(request, "L'avis ne peut pas être vide.")
            return redirect('support')

    if request.method == 'POST' and not request.user.is_authenticated:
        messages.error(request, "Connectez-vous pour envoyer un message au support.")
        return redirect('support')

    if request.method == 'POST' and request.user.is_authenticated:
        contenu = request.POST.get('message', '').strip()
        sujet = request.POST.get('sujet', 'Support')
        if contenu:
            MessageSupport.objects.create(
                user=request.user,
                contenu=f"[{sujet}] {contenu}",
                est_admin=False
            )
            notifier(request.user, "Message envoyé", "Votre message a été envoyé au support.", "INFO", url=reverse('chat_support'))
            for admin in User.objects.filter(is_staff=True):
                notifier(admin, "Nouveau message client", f"{request.user.username}: {contenu[:80]}", "INFO", url=f"{reverse('chat_support_admin')}?user={request.user.id}")
            messages.success(request, "Message envoyé au support.")
            return redirect('support')
        else:
            messages.error(request, "Le message ne peut pas être vide.")

    return render(request, 'scoring/support.html', {'messages_support': messages_support})

def page_a_propos(request):
    return render(request, 'scoring/a_propos.html')

def page_tarifs(request):
    profil_client = None
    if request.user.is_authenticated:
        profil_client = ProfilClient.objects.filter(user=request.user).first()
    return render(request, 'scoring/tarifs.html', {'profil_client': profil_client})

def page_faq(request):
    return render(request, 'scoring/faq.html')

def page_carrieres(request):
    return render(request, 'scoring/carrieres.html')

def page_presse(request):
    return render(request, 'scoring/presse.html')

def page_partenaires(request):
    return render(request, 'scoring/partenaires.html')

def page_apis(request):
    return render(request, 'scoring/apis.html')

def page_mentions_legales(request):
    return render(request, 'scoring/mentions_legales.html')

def page_confidentialite(request):
    return render(request, 'scoring/confidentialite.html')

def page_cookies(request):
    return render(request, 'scoring/cookies.html')

@login_required
def projet_immobilier(request):
    profil, _ = ProfilClient.objects.get_or_create(user=request.user, defaults={
        'abonnement': 'ESSENTIEL',
        'prochaine_facturation': timezone.now().date() + timedelta(days=30)
    })
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()
    return render(request, 'scoring/projet_immobilier.html', {
        'profil_client': profil,
        'unread_notifs': unread_notifs
    })

# ==============================================================================
# 5. PROFIL & ADMIN DASHBOARD
# ==============================================================================

@login_required
def profil(request):
    client_profil, created = ProfilClient.objects.get_or_create(user=request.user)
    comptes = Compte.objects.filter(user=request.user, est_actif=True)
    password_form = PasswordChangeForm(request.user)
    messages_support = MessageSupport.objects.filter(user=request.user).order_by('-date_envoi')[:5]
    unread_notifs = Notification.objects.filter(user=request.user, est_lu=False).count()

    if request.method == 'POST':
        if 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Votre mot de passe a été mis à jour avec succès.")
                return redirect('profil')
            else:
                messages.error(request, "Erreur lors du changement de mot de passe. Vérifiez les champs.")
        
        elif 'update_info' in request.POST:
            try:
                request.user.first_name = request.POST.get('first_name')
                ln = request.POST.get('last_name')
                request.user.last_name = ln.upper() if ln else ''
                request.user.email = request.POST.get('email')
                request.user.save()

                client_profil.telephone = request.POST.get('telephone')
                client_profil.ville_naissance = request.POST.get('ville') 
                client_profil.save()

                messages.success(request, "Vos informations ont été mises à jour.")
                return redirect('profil')
            except Exception as e:
                messages.error(request, f"Une erreur est survenue lors de la mise à jour : {e}")

    return render(request, 'scoring/profil.html', {
        'profil': client_profil,
        'comptes': comptes,
        'password_form': password_form,
        'messages_support': messages_support,
        'unread_notifs': unread_notifs
    })

@staff_member_required
def admin_dashboard_view(request):
    total_users = User.objects.count()
    total_balance = Compte.objects.filter(est_actif=True).aggregate(total_sum=Sum('solde'))['total_sum'] or 0.00
    recent_transactions = Transaction.objects.all().select_related('compte', 'compte__user').order_by('-date_execution')[:10]
    pending_loans = DemandeCredit.objects.filter(statut='EN_ATTENTE').count()
    active_accounts = Compte.objects.filter(est_actif=True).count()
    
    top_categories = Transaction.objects.filter(type='DEBIT').values('categorie').annotate(
        total_spent=Sum(F('montant'))
    ).order_by('total_spent')[:5]
    
    category_map = dict(Transaction.CATEGORIE_CHOICES)

    context = {
        'total_users': total_users,
        'total_balance': total_balance,
        'pending_loans': pending_loans,
        'active_accounts': active_accounts,
        'recent_transactions': recent_transactions,
        'top_categories': [
            {'name': category_map.get(item['categorie'], 'Inconnu'), 'total': abs(item['total_spent'])}
            for item in top_categories
        ],
        'admin_url_base': '/admin/' 
    }
    return render(request, 'scoring/admin_dashboard.html', context)

# Dans scoring/views.py (Ajoutez à la fin)

def produits_comptes(request):
    return render(request, 'scoring/produits/comptes.html')

def produits_cartes(request):
    return render(request, 'scoring/produits/cartes.html')

def produits_epargne(request):
    return render(request, 'scoring/produits/epargne.html')
