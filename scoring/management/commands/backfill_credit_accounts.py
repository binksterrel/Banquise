from django.core.management.base import BaseCommand

from scoring.models import Compte, DemandeCredit


class Command(BaseCommand):
    help = "Renseigne le compte_versement des demandes de crédit avec le premier compte actif de l'utilisateur."

    def handle(self, *args, **options):
        updated = 0
        missing_account = 0

        for demande in DemandeCredit.objects.select_related('user').all():
            if demande.compte_versement_id:
                continue

            compte = (
                Compte.objects.filter(user=demande.user, est_actif=True)
                .order_by('id')
                .first()
            )

            if compte:
                demande.compte_versement = compte
                demande.save(update_fields=['compte_versement'])
                updated += 1
            else:
                missing_account += 1

        self.stdout.write(self.style.SUCCESS(f"Comptes mis à jour : {updated}"))
        if missing_account:
            self.stdout.write(self.style.WARNING(f"Demandes sans compte actif : {missing_account}"))
