from .models import Notification


def notifications_context(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {
            "unread_notifications_count": 0,
            "recent_notifications": [],
        }

    qs = Notification.objects.filter(recipient=user)
    unread_count = qs.filter(is_read=False).count()
    recent = list(qs.select_related("actor")[:6])
    return {
        "unread_notifications_count": unread_count,
        "recent_notifications": recent,
    }
