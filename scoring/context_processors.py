from .models import Notification


def unread_notifications(request):
    """Expose le nombre de notifications non lues dans tous les templates."""
    if request.user.is_authenticated:
        return {'unread_notifs': Notification.objects.filter(user=request.user, est_lu=False).count()}
    return {'unread_notifs': 0}
