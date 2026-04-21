from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone

import aiohttp
from celery import shared_task
from django.conf import settings
from django.contrib.auth import get_user_model

from users.models import Notification


User = get_user_model()


async def _tg_send_message(*, token: str, chat_id: str, text: str) -> tuple[bool, str]:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "disable_web_page_preview": True}
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(url, json=payload) as resp:
                body = await resp.text()
                if resp.status == 200:
                    return True, body
                return False, f"{resp.status} {body[:300]}"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def _notif_to_text(n: Notification) -> str:
    pl = n.payload or {}
    base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    kind = str(n.kind)
    nk = Notification.Kind

    if kind == nk.DM_MESSAGE:
        frm = (pl.get("from_username") or "").strip()
        preview = (pl.get("preview") or "").strip()
        return f"✉️ Yangi xabar\n\n@{frm}\n{preview}".strip()

    if kind == nk.YAQIN_REQUEST:
        frm = (pl.get("from_username") or "").strip()
        link = f"{base}/profile/{frm}/" if base and frm else ""
        return f"🤝 Yaqinlik so‘rovi\n\n@{frm}\n{link}".strip()

    if kind == nk.COLLAB_INVITE:
        owner = (pl.get("post_owner_username") or "").strip()
        pid = pl.get("post_id")
        link = f"{base}/profile/{owner}/?post={pid}" if base and owner and pid else ""
        return f"👥 Hammualliflik taklifi\n\n@{owner}\n{link}".strip()

    if kind == nk.COMMENT:
        frm = (pl.get("from_username") or "").strip()
        owner = (pl.get("post_owner_username") or "").strip()
        pid = pl.get("post_id")
        link = f"{base}/profile/{owner}/post/{pid}/" if base and owner and pid else ""
        return f"💬 Yangi izoh\n\n@{frm}\n{link}".strip()

    if kind == nk.NEW_POST:
        owner = (pl.get("post_owner_username") or "").strip()
        pid = pl.get("post_id")
        title = (pl.get("title") or "").strip()
        link = f"{base}/profile/{owner}/post/{pid}/" if base and owner and pid else ""
        head = f"📝 Yangi post: @{owner}"
        if title:
            head += f"\n{title}"
        return f"{head}\n{link}".strip()

    return (pl.get("text") or "🔔 Bildirishnoma").strip()


def _mark_bot_status(n: Notification, *, ok: bool, info: str) -> None:
    pl = dict(n.payload or {})
    pl["bot_sent"] = bool(ok)
    pl["bot_sent_at"] = datetime.now(timezone.utc).isoformat()
    if ok:
        pl.pop("bot_error", None)
    else:
        pl["bot_error"] = info[:500]
    n.payload = pl
    n.save(update_fields=["payload"])


@shared_task
def send_notification_to_telegram(*, notification_id: int) -> None:
    token = (os.environ.get("BOT_TOKEN", "") or "").strip()
    if not token:
        return
    try:
        n = Notification.objects.select_related("user").get(pk=notification_id)
    except Notification.DoesNotExist:
        return
    pl = n.payload or {}
    if pl.get("bot_sent") is True:
        return
    chat_id = (getattr(n.user, "telegram_id", "") or "").strip()
    if not chat_id:
        return
    text = _notif_to_text(n)
    ok, info = asyncio.run(_tg_send_message(token=token, chat_id=chat_id, text=text))
    _mark_bot_status(n, ok=ok, info=info)


@shared_task
def create_notification(*, user_id: int, kind: str, payload: dict) -> None:
    n = Notification.objects.create(user_id=user_id, kind=kind, payload=payload or {})
    try:
        send_notification_to_telegram.delay(notification_id=int(n.pk))
    except Exception:
        pass


@shared_task
def ensure_yaqin_request_notification(*, from_user_id: int, to_user_id: int) -> None:
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
    n = Notification.objects.create(
        user_id=to_user_id,
        kind=Notification.Kind.YAQIN_REQUEST,
        payload={"from_user_id": u.id, "from_username": u.username},
    )
    try:
        send_notification_to_telegram.delay(notification_id=int(n.pk))
    except Exception:
        pass

