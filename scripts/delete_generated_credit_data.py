import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "Banquise.settings")
django.setup()

from django.contrib.auth.models import User
from scoring.models import DemandeCredit


def main():
    prefixes = ["ia_user_", "demo_user_"]
    deleted = []
    for username in User.objects.filter(username__startswith=prefixes[0]).values_list("username", flat=True):
        user = User.objects.get(username=username)
        DemandeCredit.objects.filter(user=user).delete()
        user.delete()
        deleted.append(username)
    for prefix in prefixes[1:]:
        for username in User.objects.filter(username__startswith=prefix).values_list("username", flat=True):
            user = User.objects.get(username=username)
            DemandeCredit.objects.filter(user=user).delete()
            user.delete()
            deleted.append(username)
    if deleted:
        print("Supprimé les utilisateurs/demandes :", ", ".join(deleted))
    else:
        print("Aucun utilisateur généré trouvé.")


if __name__ == "__main__":
    main()
