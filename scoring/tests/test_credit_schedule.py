import datetime
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from scoring.models import DemandeCredit, ProduitPret
from scoring.views import next_installment_date


class CreditScheduleTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="testpass")
        self.produit = ProduitPret.objects.create(nom="Test", taux_ref=Decimal("2.5"))

    def test_next_installment_starts_next_month(self):
        accept_date = datetime.date(2025, 1, 15)
        credit = DemandeCredit.objects.create(
            user=self.user,
            produit=self.produit,
            statut="ACCEPTEE",
            montant_souhaite=10000,
            duree_souhaitee_annees=1,
            mensualite_calculee=Decimal("850"),
            date_acceptation=accept_date,
        )
        self.assertEqual(next_installment_date(credit), datetime.date(2025, 2, 1))

    def test_next_installment_shifts_with_paid_installments(self):
        accept_date = datetime.date(2025, 1, 15)
        credit = DemandeCredit.objects.create(
            user=self.user,
            produit=self.produit,
            statut="ACCEPTEE",
            montant_souhaite=10000,
            duree_souhaitee_annees=1,
            mensualite_calculee=Decimal("850"),
            date_acceptation=accept_date,
            echeances_payees=1,
        )
        self.assertEqual(next_installment_date(credit), datetime.date(2025, 3, 1))

    def test_no_next_installment_when_all_paid(self):
        accept_date = datetime.date(2025, 1, 15)
        credit = DemandeCredit.objects.create(
            user=self.user,
            produit=self.produit,
            statut="ACCEPTEE",
            montant_souhaite=10000,
            duree_souhaitee_annees=1,
            mensualite_calculee=Decimal("850"),
            date_acceptation=accept_date,
            echeances_payees=12,
        )
        self.assertIsNone(next_installment_date(credit))
