from decimal import Decimal
from django.urls import reverse
from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone
from scoring.models import Compte, Transaction, Beneficiaire, DemandeCredit, ProduitPret, TypeEmploi, TypeLogement, VirementProgramme

class TestVirementViews(TestCase):
    def setUp(self):
        # Users
        self.user1 = User.objects.create_user(username='alice', password='password123', first_name='Alice')
        self.user2 = User.objects.create_user(username='bob', password='password123', first_name='Bob')
        
        # Comptes (Alice a 2 comptes, Bob en a 1)
        self.compte_alice1 = Compte.objects.create(
            user=self.user1, type_compte='COURANT', solde=1000, numero_compte='FR76ALICE1', est_actif=True
        )
        self.compte_alice2 = Compte.objects.create(
            user=self.user1, type_compte='EPARGNE', solde=5000, numero_compte='FR76ALICE2', est_actif=True
        )
        self.compte_bob = Compte.objects.create(
            user=self.user2, type_compte='COURANT', solde=100, numero_compte='FR76BOB1', est_actif=True
        )
        
        self.client = Client()
        self.client.login(username='alice', password='password123')

    def test_virement_interne_succès(self):
        """Alice vire de son compte COURANT vers son compte EPARGNE."""
        url = reverse('virement')
        data = {
            'compte_emetteur': self.compte_alice1.id,
            'montant': '200.00',
            'motif': 'Epargne',
            'nouveau_beneficiaire_iban': self.compte_alice2.numero_compte,
            'execution_date': timezone.now().date()
        }
        response = self.client.post(url, data, follow=True)
        self.assertRedirects(response, reverse('dashboard'))
        
        self.compte_alice1.refresh_from_db()
        self.compte_alice2.refresh_from_db()
        
        self.assertEqual(self.compte_alice1.solde, Decimal("800.00"))
        self.assertEqual(self.compte_alice2.solde, Decimal("5200.00"))
        
        # Vérification des transactions
        tx_debit = Transaction.objects.filter(compte=self.compte_alice1, type='DEBIT').last()
        self.assertIsNotNone(tx_debit)
        self.assertEqual(tx_debit.montant, Decimal("-200.00"))

    def test_virement_vers_tiers_succès(self):
        """Alice vire vers Bob via son IBAN."""
        url = reverse('virement')
        data = {
            'compte_emetteur': self.compte_alice1.id,
            'montant': '100.00',
            'motif': 'Cadeau Bob',
            'nouveau_beneficiaire_iban': self.compte_bob.numero_compte,
             'execution_date': timezone.now().date()
        }
        response = self.client.post(url, data, follow=True)
        self.assertRedirects(response, reverse('dashboard'))
        
        self.compte_alice1.refresh_from_db()
        self.compte_bob.refresh_from_db()
        
        self.assertEqual(self.compte_alice1.solde, Decimal("900.00"))
        self.assertEqual(self.compte_bob.solde, Decimal("200.00"))

    def test_virement_solde_insuffisant(self):
        """Alice essaie de virer plus qu'elle n'a."""
        url = reverse('virement')
        data = {
            'compte_emetteur': self.compte_alice1.id,
            'montant': '2000.00', # > 1000
            'motif': 'Trop cher',
            'nouveau_beneficiaire_iban': self.compte_bob.numero_compte,
            'execution_date': timezone.now().date()
        }
        response = self.client.post(url, data, follow=True)
        # Ne doit pas rediriger vers dashboard (succès) mais rester sur virement ou afficher erreur
        # Dans la vue actuelle, cela `messages.error` et recharge la page virement
        # (le code fait un render virement.html en cas d'erreur)
        self.assertEqual(response.status_code, 200) 
        messages = list(response.context['messages'])
        self.assertTrue(any("Solde insuffisant" in str(m) for m in messages))
        
        self.compte_alice1.refresh_from_db()
        self.assertEqual(self.compte_alice1.solde, 1000)

    def test_virement_iban_inconnu(self):
        """Virement vers un IBAN qui n'existe pas dans la banque."""
        # Note: Dans `_execute_virement`, si compte destinataire local non trouvé => pass (traité comme externe ?)
        # Mais le code actuel : 
        # `if target_iban: compte_destinataire = find...`
        # `if destinataire_locked: ...`
        # Si pas trouvé, il débite l'émetteur mais ne crédite personne (simulation virement sortant SEPA)
        
        url = reverse('virement')
        data = {
            'compte_emetteur': self.compte_alice1.id,
            'montant': '50.00',
            'motif': 'Externe',
            'nouveau_beneficiaire_iban': 'FR76INCONNU999',
            'execution_date': timezone.now().date()
        }
        response = self.client.post(url, data, follow=True)
        self.assertRedirects(response, reverse('dashboard'))
        
        self.compte_alice1.refresh_from_db()
        self.assertEqual(self.compte_alice1.solde, 950) # Débité

class TestSimulationCredit(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='charlie', password='password123')
        self.client = Client()
        self.client.login(username='charlie', password='password123')
        
        self.produit = ProduitPret.objects.create(nom="Conso", taux_ref=3.5)
        self.emploi = TypeEmploi.objects.create(nom="CDI")
        self.logement = TypeLogement.objects.create(nom="Propriétaire")
        self.compte = Compte.objects.create(user=self.user, type_compte='COURANT', est_actif=True, solde=100, numero_compte='FR76CHARLIE')

    def test_simulation_happy_path_acceptation_ia(self):
        """Simulation qui devrait passer (bons revenus, faible montant)."""
        url = reverse('simulation') # Assumant que l'url name est 'simulation' ou 'nouvelle_demande' -> check urls.py needed? 
        # Dans views.py c'est page_simulation, on suppose l'url name correspondant.
        # Si urls.py n'est pas dispo, on devine. Vu views.py reverse('resultat_simulation'), on suppose.
        # Pour être sûr, on utilise le chemin relatif ou on mock.
        
        data = {
            'montant_souhaite': 5000,
            'duree_souhaitee_annees': 2,
            'revenus_mensuels': 3000,
            'dettes_mensuelles': 0,
            'loyer_actuel': 500,
            'apport_personnel': 0,
            'produit': self.produit.id,
            'apport_personnel': 500, # +10 points bonus
            'produit': self.produit.id,
            'emploi_snapshot': self.emploi.id,
            'logement_snapshot': self.logement.id,
            'compte_versement': self.compte.id,
            'enfants_a_charge': 0,
            'jour_prelevement': 5,
            'soumise': 'on'
        }


        # Note: il faut l'URL exacte. On va assumer '/scoring/simulation/' si pattern standard.
        # Plus robuste:
        response = self.client.post('/simulation/', data, follow=True) 
        
        # Le redirect va vers resultat_simulation/<id>
        self.assertEqual(response.status_code, 200)
        
        demande = DemandeCredit.objects.filter(user=self.user).first()
        self.assertIsNotNone(demande)
        if demande.ia_decision == 'REFUSEE':
            print(f"DEBUG: Refus reason: {demande.recommendation}")
        self.assertNotEqual(demande.ia_decision, 'REFUSEE', f"Refusé avec raison: {demande.recommendation}")
        self.assertEqual(demande.montant_souhaite, 5000)
        # Vérifions que le calcul a tourné (score > 0 ou IA décision non nulle)
        # Note: sans modèle ML chargé, ça fallback sur EN_ATTENTE / 50.
        # Mais avec les règles HARD (DTI), ça ne doit pas être refusé direct.
        self.assertNotEqual(demande.ia_decision, 'REFUSEE')

    def test_simulation_refus_dti_excessif(self):
        """Simulation qui doit échouer car DTI > 45%."""
        # Mensualité pour 100k sur 10 ans ~900-1000€. Si revenus 1500, DTI ~66% => REFUS
        data = {
            'montant_souhaite': 50000,
            'duree_souhaitee_annees': 2,
            'revenus_mensuels': 3000,

            'dettes_mensuelles': 0,
            'loyer_actuel': 0,
            'produit': self.produit.id,
            'apport_personnel': 0,
            'enfants_a_charge': 0,
            'emploi_snapshot': self.emploi.id,

            'logement_snapshot': self.logement.id,
            'compte_versement': self.compte.id,
             'jour_prelevement': 5
        }
        response = self.client.post('/simulation/', data, follow=True)
        
        demande = DemandeCredit.objects.filter(user=self.user).last()
        self.assertEqual(demande.ia_decision, 'REFUSEE')
        self.assertIn("endettement excessif", demande.recommendation.lower()) # Ou check via knockout_reason logic

    def test_simulation_refus_reste_a_vivre(self):
        """Simulation qui doit échouer car reste à vivre insuffisant."""
        # Revenus 1200, Loyer 600, Crédit 200 => Reste 400. Seuil 800.
        data = {
            'montant_souhaite': 2000, # Petite mensualité
            'duree_souhaitee_annees': 1,
            'revenus_mensuels': 1200,
            'dettes_mensuelles': 0,
            'loyer_actuel': 600,
            'enfants_a_charge': 0,
            'produit': self.produit.id,
            'apport_personnel': 0,
            'emploi_snapshot': self.emploi.id,

            'logement_snapshot': self.logement.id,
            'compte_versement': self.compte.id,
             'jour_prelevement': 5
        }
        response = self.client.post('/simulation/', data, follow=True)
        
        if response.context and 'form' in response.context:
             if response.context['form'].errors:
                 print(f"DEBUG FORM ERRORS (Refus Test): {response.context['form'].errors}")

        demande = DemandeCredit.objects.filter(user=self.user).last()
        self.assertIsNotNone(demande, "Demande non créée pour refus reste à vivre")

        self.assertEqual(demande.ia_decision, 'REFUSEE')

        self.assertIn("Reste à vivre insuffisant", demande.recommendation)
