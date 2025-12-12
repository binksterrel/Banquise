from django.core.management.base import BaseCommand
from django.utils import timezone
from scoring.models import DemandeCredit


class Command(BaseCommand):
    help = "Régularise les crédits acceptés avant la gestion de date d'acceptation (définir date_acceptation, reset échéances)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Ne pas sauvegarder, afficher uniquement les crédits concernés.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        today = timezone.now().date()
        credits = DemandeCredit.objects.filter(statut="ACCEPTEE")
        updated = 0
        for cr in credits:
            original_accept = cr.date_acceptation
            if not cr.date_acceptation:
                cr.date_acceptation = cr.date_demande.date()
            # Réinitialise le suivi pour repartir proprement
            cr.echeances_payees = 0
            cr.dernier_prelevement = None
            msg = f"Credit #{cr.id} ({cr.user.username}) accept={cr.date_acceptation} (was {original_accept})"
            if dry_run:
                self.stdout.write(f"[DRY] {msg}")
            else:
                cr.save(update_fields=["date_acceptation", "echeances_payees", "dernier_prelevement"])
                self.stdout.write(f"[OK] {msg}")
                updated += 1
        if not dry_run:
            self.stdout.write(self.style.SUCCESS(f"{updated} crédit(s) régularisé(s)."))
