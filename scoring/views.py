from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required 
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db import transaction
from django.db.models import Sum, F
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
import random
import io
import json

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
from .models import Compte, Carte, Transaction, DemandeCredit, ProfilClient, ProduitPret, Beneficiaire

# BIC Statique pour la démo
BANQUISE_BIC = "BANQFR76"

# ==============================================================================
# 1. AUTHENTIFICATION
# ==============================================================================

def home(request):
    return render(request, 'scoring/home.html')

def register(request):
    if request.method == 'POST':
        form = InscriptionForm(request.POST)
        if form.is_valid():
            user = form.save()
            ProfilClient.objects.create(
                user=user,
                date_de_naissance=form.cleaned_data['birth_date'],
                ville_naissance=form.cleaned_data['birth_city']
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
            login(request, user)
            messages.success(request, "Compte créé avec succès ! 100€ offerts.")
            return redirect('dashboard')
    else:
        form = InscriptionForm()
    return render(request, 'registration/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('home')


# ==============================================================================
# 2. GESTION DES COMPTES (Dashboard, Ouvrir, Fermer, Relevé, Stats)
# ==============================================================================

@login_required
def dashboard(request):
    comptes = Compte.objects.filter(user=request.user, est_actif=True)
    cartes = Carte.objects.filter(compte__in=comptes)
    transactions = Transaction.objects.filter(compte__in=comptes).order_by('-date_execution')[:5]
    return render(request, 'scoring/dashboard.html', {
        'comptes': comptes,
        'cartes': cartes,
        'transactions_recentes': transactions
    })

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

    context = {
        'labels_json': json.dumps(labels),
        'data_json': json.dumps(data),
        'total_depenses': sum(data),
        'month_name': today.strftime('%B %Y')
    }
    return render(request, 'scoring/statistiques.html', context)

@login_required
def releve_compte(request, compte_id):
    compte = get_object_or_404(Compte, id=compte_id, user=request.user, est_actif=True)
    transactions_list = Transaction.objects.filter(compte=compte).order_by('-date_execution')
    
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
        'has_reportlab': HAS_REPORTLAB
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

                    # 2. Créditer le destinataire (si c'est un compte interne)
                    iban_cible = beneficiaire.iban if beneficiaire else nouvel_iban
                    
                    try:
                        # On cherche si un compte avec cet IBAN existe dans notre base
                        compte_destinataire = Compte.objects.get(numero_compte=iban_cible)
                        
                        # Si oui, on le crédite
                        compte_destinataire.solde += montant
                        compte_destinataire.save()

                        # Et on crée la transaction "miroir" pour que le destinataire la voie sur son relevé
                        Transaction.objects.create(
                            compte=compte_destinataire,
                            montant=montant,
                            libelle=f"Virement reçu de {request.user.first_name} {request.user.last_name} - {motif}",
                            type='CREDIT',
                            categorie='VIREMENT'
                        )
                    except Compte.DoesNotExist:
                        # Si le compte n'existe pas chez nous (virement vers une autre banque),
                        # l'argent sort simplement du système.
                        pass

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
    if request.method == 'POST':
        form = SimulationPretForm(request.POST)
        if form.is_valid():
            demande = form.save(commit=False)
            demande.user = request.user
            
            mensualite = (demande.montant_souhaite / (demande.duree_souhaitee_annees * 12))
            taux_endettement = (mensualite / demande.revenus_mensuels) * 100
            score = max(0, min(100, 100 - int(taux_endettement)))
            if demande.apport_personnel > (demande.montant_souhaite * 0.2): score += 10
            demande.score_calcule = score
            if score >= 60:
                demande.statut = 'ACCEPTEE'
                demande.recommendation = "Excellent"
            elif score >= 40:
                demande.statut = 'EN_ATTENTE'
                demande.recommendation = "Moyen"
            else:
                demande.statut = 'REFUSEE'
                demande.recommendation = "Risqué"
            
            demande.save()
            return redirect('resultat_simulation', demande_id=demande.id)
    else:
        form = SimulationPretForm()
    return render(request, 'scoring/saisie_client.html', {'form': form})

@login_required
def page_resultat(request, demande_id):
    demande = get_object_or_404(DemandeCredit, id=demande_id, user=request.user)
    mensualite_max = int(demande.revenus_mensuels * 0.35)
    return render(request, 'scoring/resultat.html', {
        'demande': demande,
        'montant_propose_formate': f"{demande.montant_souhaite:,.0f}".replace(',', ' '),
        'mensualite_max_possible': mensualite_max
    })

@login_required
def page_historique(request):
    demandes = DemandeCredit.objects.filter(user=request.user).order_by('-date_demande')
    return render(request, 'scoring/historique.html', {'demandes': demandes})

@login_required
def api_calcul_pret_dynamique(request): 
    return JsonResponse({'total_projet_formate': "---"})

@staff_member_required
def admin_stats_api(request): 
    return JsonResponse({'status': 'ok', 'message': 'API endpoint admin prêt'})


def support(request):
    return render(request, 'scoring/support.html')


# ==============================================================================
# 5. PROFIL & ADMIN DASHBOARD
# ==============================================================================

@login_required
def profil(request):
    client_profil, created = ProfilClient.objects.get_or_create(user=request.user)
    comptes = Compte.objects.filter(user=request.user, est_actif=True)
    password_form = PasswordChangeForm(request.user)

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
                request.user.last_name = request.POST.get('last_name')
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
        'password_form': password_form
    })

@staff_member_required
def admin_dashboard_view(request):
    total_users = User.objects.count()
    total_balance = Compte.objects.filter(est_actif=True).aggregate(total_sum=Sum('solde'))['total_sum'] or 0.00
    recent_transactions = Transaction.objects.all().select_related('compte', 'compte__user').order_by('-date_execution')[:10]
    pending_loans = DemandeCredit.objects.filter(statut='EN_ATTENTE').count()
    
    top_categories = Transaction.objects.filter(type='DEBIT').values('categorie').annotate(
        total_spent=Sum(F('montant'))
    ).order_by('total_spent')[:5]
    
    category_map = dict(Transaction.CATEGORIE_CHOICES)

    context = {
        'total_users': total_users,
        'total_balance': total_balance,
        'pending_loans': pending_loans,
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