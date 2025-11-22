from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from scoring.models import Compte, Transaction
from scoring.utils import overdraft_limit_for_user


class Command(BaseCommand):
    help = "Envoie hebdo un rapport simplifié aux administrateurs (comptes à surveiller + top catégories)."

    def handle(self, *args, **options):
        User = get_user_model()
        admin_emails = list(User.objects.filter(is_staff=True).exclude(email__exact='').values_list('email', flat=True))
        if not admin_emails:
            self.stdout.write("Aucun email d'admin configuré.")
            return

        now = timezone.now()
        week_ago = now - timedelta(days=7)
        comptes_alertes = []
        for compte in Compte.objects.select_related('user').filter(est_actif=True):
            limite = overdraft_limit_for_user(compte.user)
            if compte.solde < -limite or compte.solde < Decimal("50.00"):
                comptes_alertes.append(
                    f"{compte.user.username} ({compte.numero_compte}) · solde {compte.solde} € / limite {limite} €"
                )

        top_categories = Transaction.objects.filter(
            type='DEBIT',
            date_execution__gte=week_ago
        ).values('categorie').annotate(total=Sum('montant')).order_by('-total')[:5]

        body_lines = [
            "Banquise - Rapport hebdomadaire",
            f"Date: {now.strftime('%d/%m/%Y %H:%M')}",
            "",
            f"Comptes à surveiller ({len(comptes_alertes)}) :"
        ]

        if comptes_alertes:
            body_lines.extend([f"- {ligne}" for ligne in comptes_alertes[:10]])
        else:
            body_lines.append("Aucun compte critique cette semaine.")

        body_lines.append("")
        body_lines.append("Catégories (7 derniers jours) :")
        if top_categories:
            for cat in top_categories:
                body_lines.append(f"- {cat['categorie']} : {abs(cat['total'])} €")
        else:
            body_lines.append("- Pas de dépense remontée.")

        send_mail(
            subject="Banquise - rapport hebdo",
            message="\n".join(body_lines),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'webmaster@localhost'),
            recipient_list=admin_emails,
            fail_silently=False
        )
        self.stdout.write(f"Email envoyé aux admins ({len(admin_emails)} destinataires).")
