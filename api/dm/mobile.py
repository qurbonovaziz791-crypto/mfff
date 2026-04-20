from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from ninja import Router, Schema

from api.auth import MobileOrSessionAuth
from users import dm_storage
from users.models import DMThread, Notification, YaqinRequest

User = get_user_model()

router = Router(tags=["mobile", "dm"])
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


def _yaqin_accepted(u1: User, u2: User) -> bool:
    if u1.pk == u2.pk:
        return False
    return YaqinRequest.objects.filter(status=YaqinRequest.Status.ACCEPTED).filter(
        (Q(from_user=u1) & Q(to_user=u2)) | (Q(from_user=u2) & Q(to_user=u1))
    ).exists()


class ThreadRowOut(Schema):
    peer_id: int
    peer_username: str
    peer_display_name: str = ""
    peer_photo_url: str = ""
    last_preview: str = ""
    updated_at: str
    unread: int = 0


class InboxOut(Schema):
    threads: list[ThreadRowOut]


@router.get("/inbox", auth=auth, response=InboxOut)
def dm_inbox(request, q: str = ""):
    me: User = request.auth
    qn = (q or "").strip().lower()
    threads = list(
        DMThread.objects.filter(Q(user_low=me) | Q(user_high=me))
        .select_related("user_low", "user_high")
        .order_by("-updated_at")[:80]
    )
    out: list[ThreadRowOut] = []
    for t in threads:
        peer = t.peer_for(me)
        if qn and qn not in (peer.username or "").lower():
            continue
        unread = int(t.unread_for_low or 0) if me.id == t.user_low_id else int(t.unread_for_high or 0)
        out.append(
            ThreadRowOut(
                peer_id=int(peer.id),
                peer_username=str(peer.username),
                peer_display_name=_display_name(peer),
                peer_photo_url=_abs_media_url(request, _photo_url(peer)),
                last_preview=str(t.last_preview or ""),
                updated_at=t.updated_at.isoformat() if hasattr(t.updated_at, "isoformat") else str(t.updated_at),
                unread=unread,
            )
        )
    return InboxOut(threads=out)


class MessageOut(Schema):
    id: int
    sender_id: int
    body: str = ""
    created_at: str
    msg_type: str = "text"
    file_url: str = ""
    orig_filename: str = ""
    reply_to_id: Optional[int] = None
    reply_quote: Optional[str] = None
    edited_at: str = ""


class ThreadOut(Schema):
    peer_id: int
    peer_username: str
    peer_display_name: str = ""
    peer_photo_url: str = ""
    peer_read_id: int = 0
    last_message_id: int = 0
    messages: list[MessageOut]


@router.get("/thread/{username}", auth=auth, response={200: ThreadOut, 403: dict, 404: dict})
def dm_thread(request, username: str, limit: int = 200, before_id: Optional[int] = None):
    me: User = request.auth
    other = User.objects.filter(username=username, is_active=True).first()
    if not other:
        return 404, {"ok": False, "detail": "Not found"}
    if not _yaqin_accepted(me, other):
        return 403, {"ok": False, "detail": "Not allowed"}

    low, high = dm_storage.pair_ids(me.id, other.id)
    thread, _ = DMThread.objects.get_or_create(user_low_id=low, user_high_id=high)

    # mark read
    dm_storage.mark_thread_read(low, high, me.id)
    peer_read = dm_storage.get_read_cursor(low, high, other.id)

    msgs = dm_storage.list_visible_messages(
        low,
        high,
        viewer_id=me.id,
        limit=max(1, min(400, int(limit or 200))),
        before_id=int(before_id) if before_id else None,
    )
    # attach reply previews (cheap, batched)
    try:
        dm_storage.attach_reply_previews(low, high, msgs)
    except Exception:
        for m in msgs:
            m["reply_quote"] = None

    last_mid = int(msgs[-1]["id"]) if msgs else 0
    media_base = (getattr(request, "build_absolute_uri", None) and request.build_absolute_uri("/")) or ""
    media_base = media_base.rstrip("/")
    out: list[MessageOut] = []
    for m in msgs:
        fr = (m.get("file_relpath") or "").strip()
        file_url = ""
        if fr:
            if fr.startswith("http"):
                file_url = fr
            else:
                if not fr.startswith("/"):
                    fr = "/" + fr
                file_url = f"{media_base}{getattr(request, 'path', '')}"  # fallback
                try:
                    file_url = request.build_absolute_uri(f"/media/{fr.lstrip('/')}" if not fr.startswith("/media/") else fr)
                except Exception:
                    file_url = fr
        out.append(
            MessageOut(
                id=int(m["id"]),
                sender_id=int(m["sender_id"]),
                body=str(m.get("body") or ""),
                created_at=str(m.get("created_at") or ""),
                edited_at=str(m.get("edited_at") or ""),
                msg_type=str(m.get("msg_type") or "text"),
                file_url=file_url,
                orig_filename=str(m.get("orig_filename") or ""),
                reply_to_id=int(m["reply_to_id"]) if m.get("reply_to_id") else None,
                reply_quote=str((m.get("reply_quote") or {}).get("preview") or "") or None,
            )
        )

    # clear unread counters
    thread.clear_unread_for(me)
    thread.save(update_fields=["unread_for_low", "unread_for_high"])

    return ThreadOut(
        peer_id=int(other.id),
        peer_username=str(other.username),
        peer_display_name=_display_name(other),
        peer_photo_url=_abs_media_url(request, _photo_url(other)),
        peer_read_id=int(peer_read),
        last_message_id=int(last_mid),
        messages=out,
    )


class SendIn(Schema):
    to_username: str
    body: str = ""
    reply_to_id: Optional[int] = None


@router.post("/send", auth=auth, response={200: dict, 403: dict, 404: dict})
def dm_send(request, payload: SendIn):
    me: User = request.auth
    other = User.objects.filter(username=payload.to_username, is_active=True).first()
    if not other:
        return 404, {"ok": False, "detail": "Not found"}
    if not _yaqin_accepted(me, other):
        return 403, {"ok": False, "detail": "Not allowed"}

    low, high = dm_storage.pair_ids(me.id, other.id)
    mid = dm_storage.insert_message(
        low,
        high,
        sender_id=me.id,
        body=str(payload.body or ""),
        reply_to_id=int(payload.reply_to_id) if payload.reply_to_id else None,
    )
    thread, _ = DMThread.objects.get_or_create(user_low_id=low, user_high_id=high)
    src = dm_storage.get_message(low, high, mid) or {}
    thread.last_preview = dm_storage.preview_for_message_row(src)[:140]
    thread.last_sender = me
    thread.bump_unread_for_recipient(me)
    thread.updated_at = timezone.now()
    thread.save(update_fields=["last_preview", "last_sender", "unread_for_low", "unread_for_high", "updated_at"])

    Notification.objects.create(
        user=other,
        kind=Notification.Kind.DM_MESSAGE,
        payload={"from_username": me.username, "preview": thread.last_preview[:200]},
    )
    return {"ok": True, "message_id": int(mid)}


class EditIn(Schema):
    to_username: str
    message_id: int
    body: str


@router.post("/edit", auth=auth, response={200: dict, 400: dict, 403: dict, 404: dict})
def dm_edit(request, payload: EditIn):
    me: User = request.auth
    other = User.objects.filter(username=payload.to_username, is_active=True).first()
    if not other:
        return 404, {"ok": False, "detail": "Not found"}
    if not _yaqin_accepted(me, other):
        return 403, {"ok": False, "detail": "Not allowed"}
    low, high = dm_storage.pair_ids(me.id, other.id)
    try:
        ok = dm_storage.edit_message(low, high, message_id=int(payload.message_id), sender_id=me.id, new_body=str(payload.body or ""))
    except ValueError as e:
        return 400, {"ok": False, "detail": str(e)}
    return {"ok": bool(ok)}


class DeleteIn(Schema):
    to_username: str
    message_id: int
    scope: str = "all"  # all | me


@router.post("/delete", auth=auth, response={200: dict, 403: dict, 404: dict})
def dm_delete(request, payload: DeleteIn):
    me: User = request.auth
    other = User.objects.filter(username=payload.to_username, is_active=True).first()
    if not other:
        return 404, {"ok": False, "detail": "Not found"}
    if not _yaqin_accepted(me, other):
        return 403, {"ok": False, "detail": "Not allowed"}
    low, high = dm_storage.pair_ids(me.id, other.id)
    scope = (payload.scope or "all").strip().lower()
    if scope == "me":
        ok = dm_storage.hide_message_for_user(low, high, viewer_id=me.id, message_id=int(payload.message_id))
        return {"ok": bool(ok)}
    ok = dm_storage.soft_delete_message(low, high, message_id=int(payload.message_id), sender_id=me.id)
    return {"ok": bool(ok)}

