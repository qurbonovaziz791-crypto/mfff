from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from ninja import Router, Schema

from api.auth import MobileOrSessionAuth
from users.models import Notification, YaqinRequest

User = get_user_model()

router = Router(tags=["mobile", "yaqin"])
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


def _display_name(u: User) -> str:
    nm = (u.get_full_name() or "").strip()
    return nm or (u.username or "")


class UserRowOut(Schema):
    id: int
    username: str
    display_name: str = ""
    photo_url: str = ""
    state: str = "none"  # accepted | pending_out | pending_in | none


class YaqinListOut(Schema):
    users: list[UserRowOut]


@router.get("/list/{username}", auth=auth, response=YaqinListOut)
def yaqin_list(request, username: str):
    viewer: User = request.auth
    profile_user = User.objects.filter(username=username, is_active=True).first()
    if not profile_user:
        return YaqinListOut(users=[])

    rels = list(
        YaqinRequest.objects.filter(status=YaqinRequest.Status.ACCEPTED)
        .filter(Q(from_user=profile_user) | Q(to_user=profile_user))
        .values_list("from_user_id", "to_user_id")
    )
    ids: set[int] = set()
    for a, b in rels:
        ids.add(int(b) if int(a) == int(profile_user.pk) else int(a))

    users = list(User.objects.filter(pk__in=ids, is_active=True).only("id", "username", "first_name", "last_name", "photo"))

    # viewer relationship state
    pend_out = set(
        YaqinRequest.objects.filter(from_user=viewer, status=YaqinRequest.Status.PENDING).values_list("to_user_id", flat=True)
    )
    pend_in = set(
        YaqinRequest.objects.filter(to_user=viewer, status=YaqinRequest.Status.PENDING).values_list("from_user_id", flat=True)
    )
    acc_pairs = set(
        YaqinRequest.objects.filter(status=YaqinRequest.Status.ACCEPTED)
        .filter(Q(from_user=viewer) | Q(to_user=viewer))
        .values_list("from_user_id", "to_user_id")
    )
    accepted: set[int] = set()
    for a, b in acc_pairs:
        accepted.add(int(b) if int(a) == int(viewer.pk) else int(a))

    out: list[UserRowOut] = []
    for u in sorted(users, key=lambda x: x.username or ""):
        uid = int(u.pk)
        if uid in accepted:
            st = "accepted"
        elif uid in pend_out:
            st = "pending_out"
        elif uid in pend_in:
            st = "pending_in"
        else:
            st = "none"
        out.append(
            UserRowOut(
                id=uid,
                username=str(u.username),
                display_name=_display_name(u),
                photo_url=_abs_media_url(request, _photo_url(u)),
                state=st,
            )
        )
    return YaqinListOut(users=out)


class YaqinActionIn(Schema):
    action: str  # yaqin_request | yaqin_accept | yaqin_decline | yaqin_cancel
    username: str


@router.post("/action", auth=auth, response={200: dict, 400: dict})
def yaqin_action(request, payload: YaqinActionIn):
    viewer: User = request.auth
    act = (payload.action or "").strip()
    uname = (payload.username or "").strip()
    target = User.objects.filter(username=uname, is_active=True).first()
    if not target or target.pk == viewer.pk:
        return 400, {"ok": False, "detail": "User not found"}

    st = YaqinRequest.Status
    if act == "yaqin_request":
        if not getattr(target, "allow_yaqin_requests", True):
            return 400, {"ok": False, "detail": "Requests disabled"}
        if not YaqinRequest.objects.filter(status=st.ACCEPTED).filter(
            (Q(from_user=viewer) & Q(to_user=target)) | (Q(from_user=target) & Q(to_user=viewer))
        ).exists():
            out_exists = YaqinRequest.objects.filter(from_user=viewer, to_user=target, status=st.PENDING).exists()
            inc_exists = YaqinRequest.objects.filter(from_user=target, to_user=viewer, status=st.PENDING).exists()
            if not out_exists and not inc_exists:
                yr, created = YaqinRequest.objects.get_or_create(
                    from_user=viewer, to_user=target, defaults={"status": st.PENDING}
                )
                if created or yr.status == st.PENDING:
                    Notification.objects.create(
                        user=target,
                        kind=Notification.Kind.YAQIN_REQUEST,
                        payload={"from_user_id": viewer.id, "from_username": viewer.username},
                        created_at=timezone.now(),
                    )
        return {"ok": True, "state": "pending_out"}

    if act == "yaqin_accept":
        YaqinRequest.objects.filter(from_user=target, to_user=viewer, status=st.PENDING).update(status=st.ACCEPTED)
        return {"ok": True, "state": "accepted"}

    if act == "yaqin_decline":
        YaqinRequest.objects.filter(from_user=target, to_user=viewer, status=st.PENDING).delete()
        return {"ok": True, "state": "none"}

    if act == "yaqin_cancel":
        YaqinRequest.objects.filter(from_user=viewer, to_user=target, status=st.PENDING).delete()
        return {"ok": True, "state": "none"}

    return 400, {"ok": False, "detail": "Invalid action"}

