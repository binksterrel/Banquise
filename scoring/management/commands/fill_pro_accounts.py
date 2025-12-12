import random
import re

from django.core.management.base import BaseCommand

from scoring.models import Compte


COMPANIES = [
    {"name": "InnovaTech", "domain": "innovatech.fr"},
    {"name": "Nova Logistics", "domain": "novalogistics.fr"},
    {"name": "Hexa Conseil", "domain": "hexaconseil.fr"},
    {"name": "BlueWave Media", "domain": "bluewavemedia.fr"},
    {"name": "Alpine Foods", "domain": "alpinefoods.fr"},
    {"name": "Urban Mobility", "domain": "urbanmobility.fr"},
    {"name": "GreenPulse Energy", "domain": "greenpulse.fr"},
    {"name": "DataForge", "domain": "dataforge.fr"},
    {"name": "Atlas BTP", "domain": "atlasbtp.fr"},
    {"name": "Mistral Finance", "domain": "mistral-finance.fr"},
]


def _random_digits(n: int) -> str:
    return "".join(random.choices("0123456789", k=n))


def _slugify_company(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return slug or "pro"


class Command(BaseCommand):
    help = "Remplit les infos entreprise manquantes pour les comptes PRO avec des valeurs réalistes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Affiche les comptes concernés sans écrire en base.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Réécrit aussi les comptes déjà renseignés (utile pour remplacer les valeurs fictives).",
        )

    def handle(self, *args, **options):
        dry = options["dry_run"]
        force = options["force"]
        updated = 0
        for compte in Compte.objects.filter(type_compte="PRO"):
            fields = {}
            company = random.choice(COMPANIES)
            placeholder_nom = compte.entreprise_nom and compte.entreprise_nom.lower().startswith("entreprise ")
            if force or not compte.entreprise_nom or placeholder_nom:
                fields["entreprise_nom"] = company["name"]
            if force or not compte.entreprise_siret:
                fields["entreprise_siret"] = _random_digits(14)
            if force or not compte.entreprise_contact:
                slug = _slugify_company(company["name"])
                contact = f"contact@{company['domain']}"
                if compte.user.email:
                    contact = compte.user.email
                fields["entreprise_contact"] = contact
            if fields:
                updated += 1
                self.stdout.write(
                    f"- Compte {compte.id} ({compte.user.username}) -> {fields}"
                )
                if not dry:
                    for k, v in fields.items():
                        setattr(compte, k, v)
                    compte.save(update_fields=list(fields.keys()))

        suffix = " (dry-run)" if dry else ""
        self.stdout.write(self.style.SUCCESS(f"{updated} compte(s) PRO mis à jour{suffix}"))
