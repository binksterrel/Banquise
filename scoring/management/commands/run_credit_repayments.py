from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from scoring.views import process_credit_repayments_for_user
from scoring.models import DemandeCredit


class Command(BaseCommand):
    help = "Exécute les prélèvements de mensualités de crédits acceptés pour tous les utilisateurs."

    def handle(self, *args, **options):
        User = get_user_model()
        users_with_credits = User.objects.filter(demandecredit__statut='ACCEPTEE').distinct()
        count = 0
        for user in users_with_credits:
            process_credit_repayments_for_user(user)
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Prélèvements traités pour {count} utilisateur(s)."))
