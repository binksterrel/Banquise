from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import User
from decimal import Decimal

from .models import Compte, Carte, ProfilClient, Transaction, Notification
from .views import enforce_overdraft


class CoreFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="alice", password="pass1234", first_name="Alice", last_name="Polar")
        self.user2 = User.objects.create_user(username="bob", password="pass1234", first_name="Bob", last_name="Nord")

        ProfilClient.objects.create(user=self.user, abonnement="ESSENTIEL", prochaine_facturation=timezone.now().date())
        ProfilClient.objects.create(user=self.user2, abonnement="ESSENTIEL", prochaine_facturation=timezone.now().date())

        self.compte1 = Compte.objects.create(user=self.user, type_compte="COURANT", solde=500, numero_compte="FR7612345678901234567890123")
        self.compte2 = Compte.objects.create(user=self.user2, type_compte="COURANT", solde=100, numero_compte="FR7612345678901234567890999")

        self.carte1 = Carte.objects.create(compte=self.compte1, numero_visible="1234", date_expiration=timezone.now().date(), plafond_paiement=2000, plafond_retrait=500, est_bloquee=False)
        self.staff = User.objects.create_user(username="admin", password="pass1234", is_staff=True)

    def test_login_flow(self):
        resp = self.client.post(reverse("login"), {"username": "alice", "password": "pass1234"}, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.wsgi_request.user.is_authenticated)

    def test_virement_interne(self):
        self.client.login(username="alice", password="pass1234")
        data = {
            "compte_emetteur": self.compte1.id,
            "montant": "50.00",
            "motif": "Test interne",
            "nouveau_beneficiaire_iban": self.compte2.numero_compte,
        }
        resp = self.client.post(reverse("virement"), data, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.compte1.refresh_from_db()
        self.compte2.refresh_from_db()
        self.assertEqual(self.compte1.solde, 450)
        self.assertEqual(self.compte2.solde, 150)

    def test_changer_abonnement(self):
        self.client.login(username="alice", password="pass1234")
        resp = self.client.post(reverse("changer_abonnement"), {"plan": "PLUS"}, follow=False)
        self.assertEqual(resp.status_code, 302)
        profil = ProfilClient.objects.get(user=self.user)
        self.assertEqual(profil.abonnement, "PLUS")
        self.assertTrue(Transaction.objects.filter(compte=self.compte1, libelle__icontains="Abonnement").exists())

    def test_admin_toggle_card(self):
        self.client.force_login(self.staff)
        resp = self.client.post(reverse("admin_manage"), {"action": "toggle_card", "target_id": self.carte1.id}, follow=False)
        self.assertEqual(resp.status_code, 302)
        self.carte1.refresh_from_db()
        self.assertTrue(self.carte1.est_bloquee)


class OverdraftRulesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="eve", password="pass1234", first_name="Eve", last_name="Nord")
        ProfilClient.objects.create(user=self.user, abonnement="ESSENTIEL", prochaine_facturation=timezone.now().date())
        self.compte = Compte.objects.create(
            user=self.user,
            type_compte="COURANT",
            solde=Decimal("-200.00"),
            numero_compte="FR7612345678900000000000001"
        )
        self.carte = Carte.objects.create(
            compte=self.compte,
            numero_visible="9999",
            date_expiration=timezone.now().date(),
            plafond_paiement=2000,
            plafond_retrait=500,
            est_bloquee=False
        )

    def test_overdraft_blocks_cards_and_notifies(self):
        enforce_overdraft(self.compte)
        self.carte.refresh_from_db()
        self.assertTrue(self.carte.est_bloquee)
        notif = Notification.objects.filter(user=self.user, titre__icontains="Découvert dépassé").first()
        self.assertIsNotNone(notif)
        self.assertEqual(notif.type, "TRANSACTION")

    def test_overdraft_unblocks_when_balance_ok(self):
        # carte bloquée puis solde revenu au-dessus du seuil
        self.carte.est_bloquee = True
        self.carte.save(update_fields=["est_bloquee"])
        self.compte.solde = Decimal("50.00")
        self.compte.save(update_fields=["solde"])

        enforce_overdraft(self.compte)
        self.carte.refresh_from_db()
        self.assertFalse(self.carte.est_bloquee)
        notif = Notification.objects.filter(user=self.user, titre__icontains="Cartes débloquées").first()
        self.assertIsNotNone(notif)
