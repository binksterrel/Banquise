from ..models import Notification

def notifier(user, titre, contenu, type_evt='INFO', url=''):
    Notification.objects.create(
        user=user,
        titre=titre,
        contenu=contenu,
        type=type_evt,
        url=url or ''
    )
