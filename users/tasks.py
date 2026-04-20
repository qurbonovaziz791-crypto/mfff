from __future__ import annotations

from celery import shared_task
from django.contrib.auth import get_user_model
from users.models import Notification


User = get_user_model()


@shared_task
def create_notification(*, user_id: int, kind: str, payload: dict) -> None:
    Notification.objects.create(user_id=user_id, kind=kind, payload=payload or {})


@shared_task
def ensure_yaqin_request_notification(*, from_user_id: int, to_user_id: int) -> None:
    # So‘nggi 40 ta ichida xuddi shu yuboruvchidan kutilayotgan bildirishnoma bo‘lsa qayta yaratmaymiz.
    qs = (
        Notification.objects.filter(user_id=to_user_id, kind=Notification.Kind.YAQIN_REQUEST)
        .order_by("-created_at")[:40]
    )
    for n in qs:
        try:
            if int((n.payload or {}).get("from_user_id", 0)) == int(from_user_id):
                return
        except (TypeError, ValueError):
            continue
    try:
        u = User.objects.only("id", "username").get(pk=from_user_id)
    except User.DoesNotExist:
        return
    Notification.objects.create(
        user_id=to_user_id,
        kind=Notification.Kind.YAQIN_REQUEST,
        payload={"from_user_id": u.id, "from_username": u.username},
    )

