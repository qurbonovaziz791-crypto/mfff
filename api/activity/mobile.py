from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.utils import timezone
from ninja import Router, Schema

from api.auth import MobileOrSessionAuth
from users.models import Notification

User = get_user_model()

router = Router(tags=["mobile", "activity"])
auth = MobileOrSessionAuth()


def _photo_url(u: User) -> str:
    try:
        if getattr(u, "photo", None) and u.photo:
            return u.photo.url
    except Exception:
        return ""
    return ""


def _abs_media_url(request, maybe_path: str) -> str:
    raw = (maybe_path or "").strip()
    if not raw:
        return ""
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    if raw.startswith("/"):
        try:
            return request.build_absolute_uri(raw)
        except Exception:
            return raw
    return raw


class ActorOut(Schema):
    id: int
    username: str
    display_name: str = ""
    photo_url: str = ""


class NotificationOut(Schema):
    id: int
    kind: str
    payload: dict
    created_at: str
    read_at: Optional[str] = None
    actor: Optional[ActorOut] = None


class ActivityOut(Schema):
    items: list[NotificationOut]
    unread_count: int


@router.get("/", auth=auth, response=ActivityOut)
def activity_list(request, limit: int = 60):
    me: User = request.auth
    lim = max(1, min(120, int(limit or 60)))
    qs = list(Notification.objects.filter(user=me).order_by("-created_at")[:lim])
    unread_count = Notification.objects.filter(user=me, read_at__isnull=True).count()

    # build actor map from payload usernames
    usernames: set[str] = set()
    for n in qs:
        pl = n.payload or {}
        u = pl.get("from_username") or pl.get("post_owner_username")
        if isinstance(u, str) and u.strip():
            usernames.add(u.strip())
    user_map = {u.username: u for u in User.objects.filter(username__in=list(usernames)).only("id", "username", "first_name", "last_name", "photo")}

    items: list[NotificationOut] = []
    for n in qs:
        pl = n.payload or {}
        actor_username = (pl.get("from_username") or pl.get("post_owner_username") or "").strip()
        actor_user = user_map.get(actor_username) if actor_username else None
        actor = None
        if actor_user:
            actor = ActorOut(
                id=int(actor_user.id),
                username=str(actor_user.username),
                display_name=((actor_user.get_full_name() or "").strip() or actor_user.username),
                photo_url=_abs_media_url(request, _photo_url(actor_user)),
            )
        items.append(
            NotificationOut(
                id=int(n.id),
                kind=str(n.kind),
                payload=dict(pl),
                created_at=n.created_at.isoformat() if hasattr(n.created_at, "isoformat") else str(n.created_at),
                read_at=n.read_at.isoformat() if n.read_at else None,
                actor=actor,
            )
        )
    return ActivityOut(items=items, unread_count=int(unread_count))


@router.post("/mark-all-read", auth=auth, response={200: dict})
def mark_all_read(request):
    me: User = request.auth
    now = timezone.now()
    Notification.objects.filter(user=me, read_at__isnull=True).update(read_at=now)
    return {"ok": True, "read_at": now.isoformat()}

