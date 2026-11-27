from .models import Notification


def display_name(user):
    if not user:
        return "Someone"
    full = f"{user.first_name} {user.last_name}".strip()
    return full or user.email or user.username


def notify_user(recipient, *, category, title, body="", target_url="", actor=None):
    if not recipient or not getattr(recipient, "is_active", True):
        return None
    if actor and recipient.pk == actor.pk:
        return None
    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        category=category,
        title=title[:160],
        body=body[:280],
        target_url=target_url[:255],
    )


def notify_users(recipients, *, category, title, body="", target_url="", actor=None):
    seen_ids = set()
    rows = []
    actor_id = actor.pk if actor else None
    for user in recipients:
        if not user or not getattr(user, "is_active", True):
            continue
        if user.pk == actor_id or user.pk in seen_ids:
            continue
        seen_ids.add(user.pk)
        rows.append(
            Notification(
                recipient=user,
                actor=actor,
                category=category,
                title=title[:160],
                body=body[:280],
                target_url=target_url[:255],
            )
        )
    if rows:
        Notification.objects.bulk_create(rows)
    return rows
