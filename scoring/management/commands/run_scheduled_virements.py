import uuid
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from scoring.models import VirementProgramme
from scoring.views import _execute_virement


class Command(BaseCommand):
    help = "Exécute les virements programmés échus (prochaine_execution <= aujourd'hui)."

    def handle(self, *args, **options):
        today = timezone.now().date()
        qs = VirementProgramme.objects.filter(actif=True, prochaine_execution__lte=today)
        count = 0
        for vp in qs:
            try:
                _execute_virement(
                    compte=vp.compte_emetteur,
                    montant=vp.montant,
                    motif=vp.motif,
                    target_iban=vp.cible_iban,
                    target_phone=vp.cible_phone,
                    beneficiaire=vp.beneficiaire,
                    request_user=vp.user,
                    operation_id=uuid.uuid4().hex,
                )
                vp.derniere_execution = timezone.now()
                if vp.recurrence == 'MENSUEL':
                    vp.prochaine_execution = vp.prochaine_execution + timedelta(days=30)
                else:
                    vp.actif = False
                vp.save(update_fields=['derniere_execution', 'prochaine_execution', 'actif'])
                count += 1
            except Exception as e:
                self.stderr.write(f"[run_scheduled_virements] échec id={vp.id} user={vp.user.username} : {e}")
        self.stdout.write(self.style.SUCCESS(f"{count} virement(s) programmé(s) exécuté(s)."))
