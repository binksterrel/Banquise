"""
Attribue un numéro de téléphone à tous les utilisateurs.

Usage :
    source venv/bin/activate
    python scripts/assign_phone_numbers.py

- Charge Django et crée le ProfilClient si manquant
- N'écrase pas un téléphone déjà renseigné
- Numérotation simple : 06 + id utilisateur sur 8 chiffres (ex: id=12 -> 0600000012)
"""
import os
import sys
from pathlib import Path
import django


# S'assure que le dossier racine du projet est dans le PYTHONPATH
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Banquise.settings")
django.setup()

from django.contrib.auth.models import User  # noqa: E402
from scoring.models import ProfilClient  # noqa: E402


def format_phone(user_id: int) -> str:
    return f"06{user_id:08d}"


def assign_phones(force: bool = True):
    """
    Assigne un téléphone à tous les utilisateurs.
    - force=True : écrase les numéros existants (pour harmoniser).
    - force=False : ne touche pas aux numéros déjà présents.
    """
    updated = 0
    for user in User.objects.all().order_by("id"):
        profil, _ = ProfilClient.objects.get_or_create(
            user=user,
            defaults={"abonnement": "ESSENTIEL"},
        )
        if force or not profil.telephone:
            profil.telephone = format_phone(user.id)
            profil.save(update_fields=["telephone"])
            updated += 1
    print(f"Téléphones attribués/mis à jour pour {updated} utilisateur(s).")


if __name__ == "__main__":
    assign_phones(force=True)
