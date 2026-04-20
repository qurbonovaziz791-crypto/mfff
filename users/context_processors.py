from __future__ import annotations

from django.db.models import Case, F, IntegerField, Q, Sum, Value, When

from users.models import DMThread, Notification


def _dm_unread_sum(user_id: int) -> int:
    row = DMThread.objects.filter(Q(user_low_id=user_id) | Q(user_high_id=user_id)).aggregate(
        s=Sum(
            Case(
                When(user_low_id=user_id, then=F("unread_for_low")),
                When(user_high_id=user_id, then=F("unread_for_high")),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
    )
    return int(row["s"] or 0)


def activity_badge(request):
    if not request.user.is_authenticated:
        return {"activity_unread_count": 0, "dm_unread_total": 0}
    n = Notification.objects.filter(user=request.user, read_at__isnull=True).count()
    return {"activity_unread_count": n, "dm_unread_total": _dm_unread_sum(request.user.id)}
