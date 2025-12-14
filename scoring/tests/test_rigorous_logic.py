from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from scoring.models import DemandeCredit, ProduitPret, TypeEmploi, TypeLogement, Compte
from django.urls import reverse

User = get_user_model()

class RigorousLogicTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='password')
        self.client.login(username='tester', password='password')
        
        self.produit = ProduitPret.objects.create(nom="Conso", taux_ref=3.5)
        self.cdi = TypeEmploi.objects.create(nom="CDI")
        self.logement = TypeLogement.objects.create(nom="Propriétaire")
        self.compte = Compte.objects.create(user=self.user, type_compte='COURANT', est_actif=True, solde=100)

    def test_solvency_rule_rejection(self):
        """Test that payment < principal/duration is fixed/rejected."""
        data = {
            'montant_souhaite': 120000,
            'duree_souhaitee_annees': 10,
            'revenus_mensuels': 5000,
            'dettes_mensuelles': 0,
            'produit': self.produit.id,
            'emploi_snapshot': self.cdi.id,
            'logement_snapshot': self.logement.id,
            'compte_versement': self.compte.id,
            'soumise': 'on',
            'jour_prelevement': 5,
            'apport_personnel': 0,
            'loyer_actuel': 0,
            'enfants_a_charge': 0,
        }
        
        response = self.client.post(reverse('simulation'), data, follow=True)
        # Check that we are redirected or success
        self.assertEqual(response.status_code, 200) 
        
        demande = DemandeCredit.objects.last()
        self.assertIsNotNone(demande, "Demande should be saved")
        # 120k / 120 months = 1000 minimum
        self.assertTrue(demande.mensualite_calculee >= 1000, 
                        f"Mensualité {demande.mensualite_calculee} should be >= 1000")

    def test_dti_cap_knockout(self):
        """Test that DTI > 45% results in refusal."""
        data = {
            'montant_souhaite': 10000,
            'duree_souhaitee_annees': 5,
            'revenus_mensuels': 2000,
            'dettes_mensuelles': 1000, 
            'produit': self.produit.id,
            'emploi_snapshot': self.cdi.id,
            'logement_snapshot': self.logement.id,
            'compte_versement': self.compte.id,
            'soumise': 'on',
            'jour_prelevement': 5,
            'apport_personnel': 0,
            'loyer_actuel': 0,
            'enfants_a_charge': 0,
        }
        self.client.post(reverse('simulation'), data, follow=True)
        demande = DemandeCredit.objects.last()
        self.assertIsNotNone(demande)
        
        self.assertEqual(demande.ia_decision, 'REFUSEE', "Should be refused due to DTI > 45%")
        self.assertEqual(demande.score_calcule, 0, "Score should be 0 on knockout")
        self.assertIn("endettement excessif", demande.recommendation)

    def test_subsistence_knockout(self):
        """Test that low Reste à Vivre results in refusal."""
        data = {
            'montant_souhaite': 10000,
            'duree_souhaitee_annees': 5,
            'revenus_mensuels': 1200,
            'dettes_mensuelles': 400,
            'enfants_a_charge': 0,
            'produit': self.produit.id,
            'emploi_snapshot': self.cdi.id,
            'logement_snapshot': self.logement.id,
            'compte_versement': self.compte.id,
            'soumise': 'on',
            'jour_prelevement': 5,
            'apport_personnel': 0,
            'loyer_actuel': 0,
        }
        self.client.post(reverse('simulation'), data, follow=True)
        demande = DemandeCredit.objects.last()
        self.assertIsNotNone(demande)
        
        self.assertEqual(demande.ia_decision, 'REFUSEE', "Should be refused due to subsistence")
        self.assertEqual(demande.score_calcule, 0)
        self.assertIn("Reste à vivre", demande.recommendation)
