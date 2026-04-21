from __future__ import annotations

import calendar
import hashlib
from datetime import date, datetime, timedelta
from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST
from difflib import SequenceMatcher

from blogs.forms import PostCreateForm
from blogs import storage as blog_storage
from blogs.models import Kayfiyat
from django.core.cache import cache
from users import dm_storage
from users.ratelimit import RateLimit, ratelimit
from users import tasks as user_tasks
from users.models import (
    Comment,
    DMThread,
    FeedPostSeen,
    Notification,
    PostCollaboration,
    Region,
    YaqinRequest,
)

User = get_user_model()


def _cache_ttl() -> int:
    try:
        return int(getattr(settings, "CACHE_TTL_SECONDS", 20) or 20)
    except Exception:
        return 20


def _rate_limit_or_429(request, rl: RateLimit) -> Optional[HttpResponse]:
    """Return 429 response if limited; otherwise None."""
    resp = ratelimit(rl)(lambda _req: HttpResponse(status=204))(request)
    if isinstance(resp, HttpResponse) and resp.status_code == 429:
        return resp
    return None


def _enrich_dm_messages(msgs: list[dict]) -> list[dict]:
    out: list[dict] = []
    media_base = settings.MEDIA_URL.rstrip("/")
    for m in msgs:
        row = dict(m)
        dt = parse_datetime(row["created_at"])
        if dt is not None:
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt, timezone.utc)
            row["created_local"] = timezone.localtime(dt)
        else:
            row["created_local"] = None
        ed_raw = row.get("edited_at") or ""
        if ed_raw:
            ed = parse_datetime(ed_raw)
            if ed is not None:
                if timezone.is_naive(ed):
                    ed = timezone.make_aware(ed, timezone.utc)
                row["edited_local"] = timezone.localtime(ed)
            else:
                row["edited_local"] = None
        else:
            row["edited_local"] = None
        rel = (row.get("file_relpath") or "").strip()
        row["file_url"] = f"{media_base}/{rel}" if rel else ""
        out.append(row)
    return out


def _attach_dm_reply_context(low: int, high: int, msgs: list[dict]) -> None:
    dm_storage.attach_reply_previews(low, high, msgs)
    for m in msgs:
        m["reply_btn_snippet"] = dm_storage.preview_for_message_row(m)


def _apply_dm_ticks(msgs: list[dict], me_id: int, peer_read_max_id: int) -> None:
    """Chap tomonda faqat o‘z xabarlarimizda ikki pitnachka (yetkazildi / o‘qilgan)."""
    for m in msgs:
        if m.get("sender_id") == me_id and not m.get("deleted_at"):
            mid = int(m.get("id") or 0)
            m["tick_status"] = "read" if mid <= peer_read_max_id else "delivered"
        else:
            m["tick_status"] = None


def _sync_dm_thread_tail(thread: DMThread, low: int, high: int) -> None:
    # o‘chirilgan/yashirilgan xabarlar preview’da chiqmasin: oxirgi ko‘rinadiganini olamiz
    tail = dm_storage.list_visible_messages(low, high, viewer_id=thread.user_low_id, limit=1)
    if not tail:
        thread.last_preview = ""
        thread.last_sender = None
    else:
        last = tail[-1]
        thread.last_preview = dm_storage.preview_for_message_row(last)
        thread.last_sender_id = last["sender_id"]


def _notify_dm_recipient(*, recipient: User, sender: User, preview: str) -> None:
    if recipient.pk == sender.pk:
        return
    # Celery bo'lsa background, bo'lmasa sync.
    try:
        user_tasks.create_notification.delay(
            user_id=int(recipient.pk),
            kind=str(Notification.Kind.DM_MESSAGE),
            payload={"from_username": sender.username, "preview": preview[:200]},
        )
    except Exception:
        Notification.objects.create(
            user=recipient,
            kind=Notification.Kind.DM_MESSAGE,
            payload={
                "from_username": sender.username,
                "preview": preview[:200],
            },
        )


def _dm_sidebar_rows(request_user: User, search_q: str = "") -> list[dict]:
    threads = list(
        DMThread.objects.filter(Q(user_low=request_user) | Q(user_high=request_user))
        .select_related("user_low", "user_high", "last_sender")
        .order_by("-updated_at")[:80]
    )
    rows: list[dict] = []
    for t in threads:
        peer = t.peer_for(request_user)
        unread = t.unread_for_low if request_user.id == t.user_low_id else t.unread_for_high
        rows.append({"thread": t, "peer": peer, "unread": int(unread or 0)})
    qn = (search_q or "").strip().lower()
    if qn:
        rows = [r for r in rows if qn in (r["peer"].username or "").lower()]
    return rows


@login_required
def dm_inbox_view(request):
    """Xabarlar: inbox (mobilda faqat ro‘yxat)."""
    q = (request.GET.get("q") or "").strip()
    return render(
        request,
        "users/dm_inbox.html",
        {
            "dm_sidebar_rows": _dm_sidebar_rows(request.user, q),
            "dm_active_username": None,
            "dm_search_q": q,
        },
    )


@login_required
def dm_thread_poll_view(request, username: str):
    """Yangi xabarlar uchun yengil polling (JSON + HTML fragment)."""
    other = get_object_or_404(User, username=username)
    if other.pk == request.user.pk or not _yaqin_accepted(request.user, other):
        return JsonResponse({"ok": False}, status=403)
    low, high = dm_storage.pair_ids(request.user.id, other.id)
    try:
        after_id = int(request.GET.get("after", "0"))
    except ValueError:
        after_id = 0
    dm_storage.mark_thread_read(low, high, request.user.id)
    peer_read = dm_storage.get_read_cursor(low, high, other.id)
    new_msgs = _enrich_dm_messages(
        dm_storage.list_visible_messages_after(
            low, high, viewer_id=request.user.id, after_id=after_id, limit=80
        )
    )
    _attach_dm_reply_context(low, high, new_msgs)
    _apply_dm_ticks(new_msgs, request.user.id, peer_read)
    fragments = [
        render_to_string(
            "includes/dm_message_bubble.html",
            {"m": m, "user": request.user, "dm_peer": other},
            request=request,
        )
        for m in new_msgs
    ]
    last_id = after_id
    if new_msgs:
        last_id = new_msgs[-1]["id"]
    return JsonResponse(
        {
            "ok": True,
            "fragments": fragments,
            "last_id": last_id,
            "peer_read_id": peer_read,
        }
    )


@login_required
def dm_thread_view(request, username: str):
    other = get_object_or_404(User, username=username)
    if other.pk == request.user.pk:
        return redirect("dm_inbox")
    if not _yaqin_accepted(request.user, other):
        messages.info(request, "Xabarlar faqat yaqinlar o‘rtasida.")
        return redirect("dm_inbox")

    low, high = dm_storage.pair_ids(request.user.id, other.id)
    thread, _created = DMThread.objects.get_or_create(
        user_low_id=low,
        user_high_id=high,
    )
    q = (request.GET.get("q") or "").strip()

    if request.method == "POST":
        act = (request.POST.get("action") or "send").strip()
        if act == "delete":
            try:
                mid = int(request.POST.get("message_id", "0"))
            except ValueError:
                mid = 0
            scope = (request.POST.get("delete_scope") or "").strip().lower()
            ok = False
            if mid:
                if scope == "me":
                    ok = dm_storage.hide_message_for_user(
                        low, high, viewer_id=request.user.id, message_id=mid
                    )
                else:
                    # faqat o‘z xabarini hamma uchun o‘chira oladi
                    ok = dm_storage.soft_delete_message(
                        low, high, message_id=mid, sender_id=request.user.id
                    )
                    if not ok:
                        # agar o‘ziniki bo‘lmasa, kamida o‘zi uchun yashiramiz
                        ok = dm_storage.hide_message_for_user(
                            low, high, viewer_id=request.user.id, message_id=mid
                        )
            if ok:
                _sync_dm_thread_tail(thread, low, high)
                thread.updated_at = timezone.now()
                thread.save(
                    update_fields=["last_preview", "last_sender_id", "updated_at"]
                )
            else:
                messages.warning(request, "Xabarni o‘chirib bo‘lmadi.")
            return redirect("dm_thread", username=username)

        if act == "edit":
            try:
                mid = int(request.POST.get("message_id", "0"))
            except ValueError:
                mid = 0
            new_body = (request.POST.get("body") or "").strip()
            try:
                ok = mid and dm_storage.edit_message(
                    low, high, message_id=mid, sender_id=request.user.id, new_body=new_body
                )
            except ValueError:
                ok = False
                messages.warning(request, "Matn bo‘sh bo‘lmasin.")
            if ok:
                _sync_dm_thread_tail(thread, low, high)
                thread.updated_at = timezone.now()
                thread.save(
                    update_fields=["last_preview", "last_sender_id", "updated_at"]
                )
            elif new_body:
                messages.warning(request, "Tahrirlab bo‘lmadi.")
            return redirect("dm_thread", username=username)

        if act == "forward":
            try:
                mid = int(request.POST.get("message_id", "0"))
            except ValueError:
                mid = 0
            to_username = (request.POST.get("to_username") or "").strip()
            to_user = User.objects.filter(username=to_username).first() if to_username else None
            if not mid or not to_user or to_user.pk == request.user.pk:
                messages.warning(request, "Forward uchun username to‘g‘ri emas.")
                return redirect("dm_thread", username=username)
            if not _yaqin_accepted(request.user, to_user):
                messages.info(request, "Forward faqat yaqinlar o‘rtasida.")
                return redirect("dm_thread", username=username)
            src = dm_storage.get_message(low, high, mid)
            if not src:
                messages.warning(request, "Xabar topilmadi.")
                return redirect("dm_thread", username=username)
            t_low, t_high = dm_storage.pair_ids(request.user.id, to_user.id)
            try:
                dm_storage.insert_existing_message(
                    t_low,
                    t_high,
                    sender_id=request.user.id,
                    body=src.get("body") or "",
                    msg_type=src.get("msg_type") or "text",
                    file_relpath=src.get("file_relpath") or "",
                    orig_filename=src.get("orig_filename") or "",
                )
            except ValueError:
                messages.warning(request, "Forward qilib bo‘lmadi.")
            else:
                t_thread, _ = DMThread.objects.get_or_create(user_low_id=t_low, user_high_id=t_high)
                _sync_dm_thread_tail(t_thread, t_low, t_high)
                t_thread.last_sender = request.user
                t_thread.bump_unread_for_recipient(request.user)
                t_thread.updated_at = timezone.now()
                t_thread.save(
                    update_fields=[
                        "last_preview",
                        "last_sender",
                        "unread_for_low",
                        "unread_for_high",
                        "updated_at",
                    ]
                )
                prev = t_thread.last_preview or ""
                _notify_dm_recipient(recipient=to_user, sender=request.user, preview=prev)
                messages.success(request, f"@{to_user.username} ga yuborildi.")
            return redirect("dm_thread", username=username)

        # send
        body = (request.POST.get("body") or "").strip()
        upload = request.FILES.get("attachment") or request.FILES.get("voice_attachment")
        as_voice = request.POST.get("voice") == "1" or bool(
            request.FILES.get("voice_attachment")
        )
        try:
            rrid = int(request.POST.get("reply_to_id") or "0")
        except ValueError:
            rrid = 0
        try:
            dm_storage.insert_message(
                low,
                high,
                sender_id=request.user.id,
                body=body,
                uploaded=upload,
                as_voice=as_voice,
                reply_to_id=rrid or None,
            )
        except ValueError as exc:
            err = str(exc).lower()
            if "file too large" in err:
                messages.warning(request, "Fayl juda katta (maks. 15 MB).")
            elif "unsupported" in err:
                messages.warning(request, "Bu fayl turiga ruxsat yo‘q.")
            else:
                messages.warning(request, "Matn yoki fayl kiriting.")
        else:
            _sync_dm_thread_tail(thread, low, high)
            thread.last_sender = request.user
            thread.bump_unread_for_recipient(request.user)
            thread.updated_at = timezone.now()
            thread.save(
                update_fields=[
                    "last_preview",
                    "last_sender",
                    "unread_for_low",
                    "unread_for_high",
                    "updated_at",
                ]
            )
            prev = thread.last_preview or ""
            _notify_dm_recipient(recipient=other, sender=request.user, preview=prev)
        return redirect("dm_thread", username=username)

    thread.clear_unread_for(request.user)
    thread.save(update_fields=["unread_for_low", "unread_for_high"])

    dm_storage.mark_thread_read(low, high, request.user.id)
    peer_read = dm_storage.get_read_cursor(low, high, other.id)

    msgs = _enrich_dm_messages(
        dm_storage.list_visible_messages(low, high, viewer_id=request.user.id, limit=400)
    )
    _attach_dm_reply_context(low, high, msgs)
    _apply_dm_ticks(msgs, request.user.id, peer_read)
    last_mid = msgs[-1]["id"] if msgs else 0
    return render(
        request,
        "users/dm_thread.html",
        {
            "dm_sidebar_rows": _dm_sidebar_rows(request.user, q),
            "dm_active_username": other.username,
            "dm_other": other,
            "dm_messages": msgs,
            "dm_thread": thread,
            "dm_search_q": q,
            "dm_last_message_id": last_mid,
        },
    )


@login_required
def user_search_view(request):
    """
    Instagram-uslubida username qidiruv.
    - GET: q param orqali natija beradi.
    - POST: yaqin so‘rovi / accept / decline / cancel (search sahifasidan).
    """
    if request.method == "POST":
        act = (request.POST.get("action") or "").strip()
        uname = (request.POST.get("username") or "").strip()
        q = (request.POST.get("q") or "").strip()
        target = User.objects.filter(username=uname).first()
        if not target or target.pk == request.user.pk:
            return redirect("user_search")

        st = YaqinRequest.Status
        if act == "yaqin_request":
            if not getattr(target, "allow_yaqin_requests", True):
                messages.info(request, "Bu foydalanuvchi yaqin so‘rovlarini o‘chirgan.")
            elif not _yaqin_accepted(request.user, target):
                out = YaqinRequest.objects.filter(
                    from_user=request.user, to_user=target, status=st.PENDING
                ).exists()
                inc = YaqinRequest.objects.filter(
                    from_user=target, to_user=request.user, status=st.PENDING
                ).exists()
                if not out and not inc:
                    yr, _created_req = YaqinRequest.objects.get_or_create(
                        from_user=request.user,
                        to_user=target,
                        defaults={"status": st.PENDING},
                    )
                    if yr.status == st.PENDING:
                        _ensure_yaqin_request_notification(from_user=request.user, to_user=target)
        elif act == "yaqin_accept":
            YaqinRequest.objects.filter(
                from_user=target, to_user=request.user, status=st.PENDING
            ).update(status=st.ACCEPTED)
        elif act == "yaqin_decline":
            YaqinRequest.objects.filter(
                from_user=target, to_user=request.user, status=st.PENDING
            ).delete()
        elif act == "yaqin_cancel":
            YaqinRequest.objects.filter(
                from_user=request.user, to_user=target, status=st.PENDING
            ).delete()

        if q:
            return redirect(f"/search/?q={q}")
        return redirect("user_search")

    q = (request.GET.get("q") or "").strip()
    if q.startswith("@"):
        q = q[1:].strip()
    rows: list[dict] = []

    def _norm(s: str) -> str:
        return "".join([c for c in (s or "").lower().strip() if c.isalnum()])

    def _score(u: User, qraw: str) -> float:
        qn = _norm(qraw)
        un = _norm(u.username)
        if not qn or not un:
            return 0.0
        if un.startswith(qn):
            return 3.5
        if qn in un:
            return 2.3
        return 1.2 * SequenceMatcher(None, qn, un).ratio()

    base = User.objects.filter(is_active=True).exclude(pk=request.user.pk)

    viewer_peers = set(_yaqin_peer_ids(request.user))
    viewer_region = getattr(request.user, "region", None)

    def _yaqin_state_maps(user_ids: list[int]):
        rels = list(
            YaqinRequest.objects.filter(
                Q(from_user=request.user, to_user_id__in=user_ids)
                | Q(to_user=request.user, from_user_id__in=user_ids)
            ).only("from_user_id", "to_user_id", "status")
        )
        pending_out = set()
        pending_in = set()
        accepted = set()
        for r in rels:
            if r.status == YaqinRequest.Status.ACCEPTED:
                other = r.to_user_id if r.from_user_id == request.user.pk else r.from_user_id
                accepted.add(int(other))
            elif r.status == YaqinRequest.Status.PENDING:
                if r.from_user_id == request.user.pk:
                    pending_out.add(int(r.to_user_id))
                elif r.to_user_id == request.user.pk:
                    pending_in.add(int(r.from_user_id))
        return accepted, pending_out, pending_in

    users: list[User] = []
    mode = "suggested" if not q else "search"

    if q:
        # Fuzzy + full-name search (Instagramga yaqin).
        q_short = q[:2]
        pool = list(
            base.filter(
                Q(username__icontains=q_short)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
            )
            .only("id", "username", "first_name", "last_name", "photo", "region", "allow_yaqin_requests")
            .order_by("username")[:220]
        )
        scored = [(u, _score(u, q)) for u in pool]
        scored.sort(key=lambda t: (t[1], t[0].username), reverse=True)
        users = [u for (u, sc) in scored if sc > 0.15][:30]
    else:
        # Suggested: same region + mutual yaqinlar.
        cand_qs = base
        if viewer_region:
            cand_qs = cand_qs.filter(region=viewer_region)
        pool = list(
            cand_qs.only("id", "username", "first_name", "last_name", "photo", "region", "allow_yaqin_requests")
            .order_by("username")[:140]
        )
        def mutual(u: User) -> int:
            # cheap-ish: only for limited pool
            u_peers = set(_yaqin_peer_ids(u))
            return len(viewer_peers.intersection(u_peers))
        scored = [(u, mutual(u)) for u in pool]
        scored.sort(key=lambda t: (t[1], t[0].username), reverse=True)
        users = [u for (u, mc) in scored if mc > 0][:20]
        if len(users) < 20:
            # fallback: active users (no region filter) to fill list
            filler = list(
                base.only("id", "username", "first_name", "last_name", "photo", "region", "allow_yaqin_requests")
                .order_by("username")[:60]
            )
            have = {u.pk for u in users}
            for u in filler:
                if u.pk in have:
                    continue
                users.append(u)
                have.add(u.pk)
                if len(users) >= 20:
                    break

    ids = [u.pk for u in users]
    accepted, pending_out, pending_in = _yaqin_state_maps(ids) if ids else (set(), set(), set())

    for u in users:
        if u.pk in accepted:
            state = "accepted"
        elif u.pk in pending_out:
            state = "pending_out"
        elif u.pk in pending_in:
            state = "pending_in"
        else:
            state = "none"
        # mutual count for UI (only meaningful for suggested mode)
        mutual_cnt = 0
        if viewer_peers and mode == "suggested":
            mutual_cnt = len(viewer_peers.intersection(set(_yaqin_peer_ids(u))))
        rows.append(
            {
                "user": u,
                "display": (u.get_full_name() or "").strip() or u.username,
                "state": state,
                "allow_requests": bool(getattr(u, "allow_yaqin_requests", True)),
                "mutual": mutual_cnt,
            }
        )

    ctx = {"q": q, "rows": rows, "mode": mode}
    if request.headers.get("HX-Request") == "true":
        return render(request, "users/includes/search_results.html", ctx)
    return render(request, "users/search.html", ctx)


@login_required
@ratelimit(RateLimit("compose", limit=40, window_seconds=60, key_func=lambda r: f"u:{r.user.pk}"))
def compose_view(request):
    """
    Yangi hissiyot/xotira yaratish uchun alohida sahifa.
    (Profil sahifasidagi + modal o‘rniga)
    """
    edit_id = None
    edit_id_raw = request.GET.get("edit") if request.method == "GET" else request.POST.get("post_id")
    if edit_id_raw not in (None, ""):
        try:
            edit_id = int(edit_id_raw)
        except (TypeError, ValueError):
            edit_id = None

    if request.method == "POST":
        action = request.POST.get("action") or "create"
        form = PostCreateForm(request.POST)
        form.fields["collaborators"].queryset = _yaqin_users_for_collab(request.user)
        if form.is_valid():
            cd = form.cleaned_data
            is_draft = action in ("draft", "draft_update")
            if edit_id and action in ("update", "draft_update"):
                blog_storage.update_post(
                    user_id=request.user.id,
                    username=request.user.username,
                    post_id=int(edit_id),
                    title=cd["title"],
                    body=cd["body"],
                    mood=cd["mood"],
                    hashtag=cd.get("hashtag") or None,
                    visibility=int(cd.get("visibility", blog_storage.VIS_PRIVATE)),
                    is_draft=is_draft,
                )
                messages.success(request, "Tahrir saqlandi.")
                return redirect("profile", username=request.user.username)

            post_id = blog_storage.create_post(
                user_id=request.user.id,
                username=request.user.username,
                title=cd["title"],
                body=cd["body"],
                mood=cd["mood"],
                hashtag=cd.get("hashtag") or None,
                parent_id=cd.get("parent") or None,
                visibility=int(cd.get("visibility", blog_storage.VIS_PRIVATE)),
                is_draft=is_draft,
            )
            if not is_draft:
                allowed = set(_yaqin_users_for_collab(request.user).values_list("pk", flat=True))
                cst = PostCollaboration.Status
                for cu in cd.get("collaborators") or []:
                    if not getattr(cu, "allow_collab_invites", True):
                        continue
                    if cu.pk not in allowed:
                        continue
                    pc_obj, created_collab = PostCollaboration.objects.get_or_create(
                        post_owner=request.user,
                        post_id=post_id,
                        collaborator=cu,
                        defaults={"status": cst.PENDING},
                    )
                    if created_collab:
                        Notification.objects.create(
                            user=cu,
                            kind=Notification.Kind.COLLAB_INVITE,
                            payload={
                                "post_owner_id": request.user.id,
                                "post_owner_username": request.user.username,
                                "post_id": post_id,
                                "collab_id": pc_obj.pk,
                            },
                        )
            messages.success(request, "Qoralama saqlandi." if is_draft else "Yangi hissiyot joylandi.")
            return redirect("profile", username=request.user.username)
    else:
        initial = {}
        is_edit = False
        if edit_id:
            post = blog_storage.get_post(
                user_id=request.user.id, username=request.user.username, post_id=int(edit_id)
            )
            if post:
                is_edit = True
                initial = {
                    "title": post.get("title") or "",
                    "body": post.get("body") or "",
                    "mood": post.get("mood") or "",
                    "hashtag": post.get("hashtag") or "",
                    "visibility": int(post.get("visibility", blog_storage.VIS_PRIVATE)),
                    "post_id": int(post.get("id")),
                }
        else:
            try:
                initial["visibility"] = int(getattr(request.user, "default_post_visibility", blog_storage.VIS_PRIVATE))
            except Exception:
                initial["visibility"] = blog_storage.VIS_PRIVATE
        form = PostCreateForm(initial=initial)
        form.fields["collaborators"].queryset = _yaqin_users_for_collab(request.user)

    k_active = Kayfiyat.objects.filter(is_active=True)
    default_mood_slug = (
        Kayfiyat.objects.filter(is_primary=True, is_active=True)
        .order_by("sort_order", "name")
        .values_list("slug", flat=True)
        .first()
        or ""
    )
    ctx = {
        "form": form,
        "kayfiyat_primary": list(k_active.filter(is_primary=True).order_by("sort_order", "name")),
        "kayfiyat_extras": list(k_active.filter(is_primary=False).order_by("sort_order", "name")),
        "default_mood_slug": default_mood_slug,
        "is_edit": bool(edit_id),
        "edit_post_id": edit_id,
        "compose_autosave_enabled": bool(getattr(request.user, "compose_autosave_enabled", True)),
    }
    return render(request, "users/compose.html", ctx)


@login_required
def archive_view(request):
    """
    Arxiv (Kalendar) — faqat o'zingizning postlaringizni oy/kun bo'yicha ko'rish.
    """
    query = request.GET.get("q")
    date_filter = request.GET.get("date")
    tag = request.GET.get("tag")

    try:
        cal_year = int(request.GET.get("cal_year", datetime.now().year))
        cal_month = int(request.GET.get("cal_month", datetime.now().month))
    except ValueError:
        cal_year, cal_month = datetime.now().year, datetime.now().month
    if cal_month < 1:
        cal_month, cal_year = 12, cal_year - 1
    if cal_month > 12:
        cal_month, cal_year = 1, cal_year + 1

    first_wd, cal_last_day = calendar.monthrange(cal_year, cal_month)
    if cal_month == 1:
        cal_prev_year, cal_prev_month = cal_year - 1, 12
    else:
        cal_prev_year, cal_prev_month = cal_year, cal_month - 1
    if cal_month == 12:
        cal_next_year, cal_next_month = cal_year + 1, 1
    else:
        cal_next_year, cal_next_month = cal_year, cal_month + 1

    posts_list = blog_storage.list_posts(
        user_id=request.user.id,
        username=request.user.username,
        is_owner=True,
        query=query,
        date_filter=date_filter,
        tag=tag,
        viewer_is_yaqin=True,
    )
    posts = list(posts_list)[:50]

    _au = request.user
    for _p in posts:
        _p["feed_author_photo_url"] = _au.photo.url if _au.photo else ""
        _p["feed_author_initial"] = (_au.username[0] if _au.username else "?").upper()
        _p["feed_author_display"] = ((_au.get_full_name() or "").strip() or _au.username)
        _p["collab_count"] = 0

    cal_counts = blog_storage.calendar_day_counts(
        user_id=request.user.id,
        username=request.user.username,
        year=cal_year,
        month=cal_month,
    )
    cal_cells: list[dict] = []
    for _ in range(int(first_wd)):
        cal_cells.append({"d": None, "n": 0})
    for d in range(1, cal_last_day + 1):
        cal_cells.append({"d": d, "n": int(cal_counts.get(d, 0))})

    years = blog_storage.available_years(user_id=request.user.id, username=request.user.username)
    if not years:
        years = [datetime.now().year]

    months = [
        (1, "Yanvar"),
        (2, "Fevral"),
        (3, "Mart"),
        (4, "Aprel"),
        (5, "May"),
        (6, "Iyun"),
        (7, "Iyul"),
        (8, "Avgust"),
        (9, "Sentyabr"),
        (10, "Oktyabr"),
        (11, "Noyabr"),
        (12, "Dekabr"),
    ]
    weekday_labels = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]
    month_total = int(sum(cal_counts.values()))

    today = datetime.now().date()
    on_this_day = blog_storage.posts_on_month_day(
        user_id=request.user.id,
        username=request.user.username,
        month=today.month,
        day=today.day,
        limit=3,
    )
    for _p in on_this_day:
        _p["feed_author_photo_url"] = _au.photo.url if _au.photo else ""
        _p["feed_author_initial"] = (_au.username[0] if _au.username else "?").upper()
        _p["feed_author_display"] = ((_au.get_full_name() or "").strip() or _au.username)
        _p["collab_count"] = 0

    ctx = {
        "posts": posts,
        "query": query,
        "date_filter": date_filter,
        "tag": tag,
        "cal_year": cal_year,
        "cal_month": cal_month,
        "cal_cells": cal_cells,
        "cal_prev_year": cal_prev_year,
        "cal_prev_month": cal_prev_month,
        "cal_next_year": cal_next_year,
        "cal_next_month": cal_next_month,
        "years": years,
        "months": months,
        "weekday_labels": weekday_labels,
        "month_total": month_total,
        "today_str": today.isoformat(),
        "on_this_day": on_this_day,
    }
    return render(request, "users/archive.html", ctx)


def _mood_stat_bars(by_mood: dict, total: int) -> list[dict]:
    if not total or not by_mood:
        return []
    max_c = max(by_mood.values())
    out: list[dict] = []
    for slug, c in sorted(by_mood.items(), key=lambda x: -x[1]):
        out.append(
            {
                "slug": slug,
                "count": c,
                "label": blog_storage.mood_label(slug),
                "pct": round(100 * c / total),
                "bar": round(100 * c / max_c) if max_c else 0,
            }
        )
    return out


@login_required
def stats_view(request):
    """
    Statistika: o'tgan hafta / o'tgan oy / o'tgan yil (shaxsiy) +
    tizim bo'yicha ochiq xotiralardan kayfiyatlar.
    """
    today = date.today()
    start_week = (today - timedelta(days=6)).isoformat()
    end_week = today.isoformat()

    if today.month == 1:
        py, pm = today.year - 1, 12
    else:
        py, pm = today.year, today.month - 1
    _, last_d = calendar.monthrange(py, pm)
    start_prev_month = date(py, pm, 1).isoformat()
    end_prev_month = date(py, pm, last_d).isoformat()

    prev_year = today.year - 1
    start_prev_year = date(prev_year, 1, 1).isoformat()
    end_prev_year = date(prev_year, 12, 31).isoformat()

    start_ytd = date(today.year, 1, 1).isoformat()
    end_ytd = today.isoformat()

    uid = request.user.id
    un = request.user.username

    streak_days = blog_storage.user_writing_streak_days(user_id=uid, username=un)
    tytd, mw_ytd = blog_storage.user_mood_stats_in_range(
        user_id=uid, username=un, date_from=start_ytd, date_to=end_ytd
    )
    tag_pairs = blog_storage.user_hashtag_top(
        user_id=uid,
        username=un,
        limit=5,
        date_from=start_ytd,
        date_to=end_ytd,
    )
    hashtag_top_ytd = [
        {"display": h, "slug": h.strip().lstrip("#").lower(), "count": c}
        for h, c in tag_pairs
    ]

    tw, mw_week = blog_storage.user_mood_stats_in_range(
        user_id=uid, username=un, date_from=start_week, date_to=end_week
    )
    tm, mw_month = blog_storage.user_mood_stats_in_range(
        user_id=uid, username=un, date_from=start_prev_month, date_to=end_prev_month
    )
    ty, mw_year = blog_storage.user_mood_stats_in_range(
        user_id=uid, username=un, date_from=start_prev_year, date_to=end_prev_year
    )

    g_all, gw_all = blog_storage.global_public_mood_stats(days=None)
    g30, gw30 = blog_storage.global_public_mood_stats(days=30)

    me_ytd = {"total": tytd, "bars": _mood_stat_bars(mw_ytd, tytd)}
    me_week = {"total": tw, "bars": _mood_stat_bars(mw_week, tw)}
    me_month = {"total": tm, "bars": _mood_stat_bars(mw_month, tm)}
    me_year = {"total": ty, "bars": _mood_stat_bars(mw_year, ty)}
    sys_all = {"total": g_all, "bars": _mood_stat_bars(gw_all, g_all)}
    sys_30 = {"total": g30, "bars": _mood_stat_bars(gw30, g30)}

    ctx = {
        "streak_days": streak_days,
        "ytd_total": tytd,
        "hashtag_top_ytd": hashtag_top_ytd,
        "me_blocks": [
            {
                "period": {
                    "label": "Joriy yil",
                    "range": f"{start_ytd} — {end_ytd}",
                },
                "data": me_ytd,
            },
            {
                "period": {
                    "label": "O‘tgan 7 kun",
                    "range": f"{start_week} — {end_week}",
                },
                "data": me_week,
            },
            {
                "period": {
                    "label": "O‘tgan oy",
                    "range": f"{start_prev_month} — {end_prev_month}",
                },
                "data": me_month,
            },
            {
                "period": {
                    "label": "O‘tgan yil",
                    "range": f"{start_prev_year} — {end_prev_year}",
                },
                "data": me_year,
            },
        ],
        "sys_blocks": [
            {"period": {"label": "Barcha vaqt"}, "data": sys_all},
            {"period": {"label": "Oxirgi 30 kun"}, "data": sys_30},
        ],
    }
    return render(request, "users/stats.html", ctx)


def _yaqin_accepted(u1, u2) -> bool:
    if not u1.is_authenticated or u1.pk == u2.pk:
        return False
    return YaqinRequest.objects.filter(status=YaqinRequest.Status.ACCEPTED).filter(
        (Q(from_user=u1) & Q(to_user=u2)) | (Q(from_user=u2) & Q(to_user=u1))
    ).exists()


def _viewer_is_yaqin(viewer, profile_user) -> bool:
    if not viewer.is_authenticated:
        return False
    return _yaqin_accepted(viewer, profile_user)


def _yaqin_count(user) -> int:
    return YaqinRequest.objects.filter(status=YaqinRequest.Status.ACCEPTED).filter(
        Q(from_user=user) | Q(to_user=user)
    ).count()


def _yaqin_peer_ids(user) -> list[int]:
    if not user.is_authenticated:
        return []
    out: list[int] = []
    for r in YaqinRequest.objects.filter(status=YaqinRequest.Status.ACCEPTED).filter(
        Q(from_user=user) | Q(to_user=user)
    ):
        out.append(r.to_user_id if r.from_user_id == user.pk else r.from_user_id)
    return out


def _yaqin_users_for_collab(user):
    ids = _yaqin_peer_ids(user)
    return User.objects.filter(pk__in=ids).order_by("username")


def _viewer_can_comment(*, viewer, post_owner) -> bool:
    if not viewer.is_authenticated:
        return False
    if viewer.pk == post_owner.pk:
        return True
    return _viewer_is_yaqin(viewer, post_owner)


def _yaqin_request_notification_exists(from_user, to_user) -> bool:
    """Bir xil yuboruvchidan kutilayotgan bildirishnoma allaqachon bormi."""
    qs = Notification.objects.filter(
        user=to_user, kind=Notification.Kind.YAQIN_REQUEST
    ).order_by("-created_at")[:40]
    for n in qs:
        try:
            if int(n.payload.get("from_user_id", 0)) == from_user.pk:
                return True
        except (TypeError, ValueError):
            continue
    return False


def _ensure_yaqin_request_notification(*, from_user, to_user) -> None:
    """So‘rov qatoridan qat’i nazar, qabul qiluvchiga bitta bildirishnoma bo‘lishini ta’minlaydi."""
    if _yaqin_request_notification_exists(from_user, to_user):
        return
    try:
        user_tasks.ensure_yaqin_request_notification.delay(
            from_user_id=int(from_user.pk),
            to_user_id=int(to_user.pk),
        )
    except Exception:
        Notification.objects.create(
            user=to_user,
            kind=Notification.Kind.YAQIN_REQUEST,
            payload={
                "from_user_id": from_user.id,
                "from_username": from_user.username,
            },
        )


def _incoming_yaqin_pending(user):
    if not user.is_authenticated:
        return []
    return list(
        YaqinRequest.objects.filter(to_user=user, status=YaqinRequest.Status.PENDING)
        .select_related("from_user")
        .order_by("-created_at")
    )


def _find_pending_collaboration(
    user,
    *,
    collab_id_raw=None,
    post_owner_username: Optional[str] = None,
    post_id_raw=None,
) -> Optional[PostCollaboration]:
    """Faoliyatdan qabul/rad: collab_id noto‘g‘ri bo‘lsa ham post muallifi + post_id bo‘yicha topish."""
    cst = PostCollaboration.Status.PENDING
    if collab_id_raw not in (None, ""):
        try:
            cid = int(collab_id_raw)
            if cid > 0:
                pc = PostCollaboration.objects.filter(pk=cid, collaborator=user, status=cst).first()
                if pc:
                    return pc
        except (TypeError, ValueError):
            pass
    uname = (post_owner_username or "").strip()
    if uname and post_id_raw not in (None, ""):
        try:
            pid = int(post_id_raw)
        except (TypeError, ValueError):
            return None
        owner = User.objects.filter(username=uname).first()
        if not owner:
            return None
        return PostCollaboration.objects.filter(
            post_owner=owner, post_id=pid, collaborator=user, status=cst
        ).first()
    return None


def _yaqin_ui_state(viewer, profile_user) -> str:
    """self | accepted | pending_out | pending_in | none | anon"""
    if not viewer.is_authenticated:
        return "anon"
    if viewer.pk == profile_user.pk:
        return "self"
    if _yaqin_accepted(viewer, profile_user):
        return "accepted"
    if YaqinRequest.objects.filter(
        from_user=viewer, to_user=profile_user, status=YaqinRequest.Status.PENDING
    ).exists():
        return "pending_out"
    if YaqinRequest.objects.filter(
        from_user=profile_user, to_user=viewer, status=YaqinRequest.Status.PENDING
    ).exists():
        return "pending_in"
    return "none"


@ratelimit(RateLimit("login", limit=12, window_seconds=60))
def login_view(request):
    if request.user.is_authenticated:
        return redirect("home_feed")

    if request.method == "POST":
        u = request.POST.get("username")
        p = request.POST.get("password")
        user = authenticate(request, username=u, password=p)
        if user is not None:
            login(request, user)
            return redirect("home_feed")
        return render(request, "users/login.html", {"error": "Noto'g'ri login yoki parol"})
    return render(request, "users/login.html")


def magic_link_auth(request, lk_uuid):
    user = get_object_or_404(User, lk_uuid=lk_uuid)
    login(request, user)
    return redirect("home_feed")


def profile_view(request, username):
    profile_user = get_object_or_404(User, username=username)
    is_owner = request.user.is_authenticated and request.user == profile_user
    viewer_is_yaqin = _viewer_is_yaqin(request.user, profile_user)

    if request.method == "POST":
        rl = RateLimit(
            "profile_post",
            limit=30,
            window_seconds=60,
            key_func=lambda r: f"u:{r.user.pk}"
            if getattr(r, "user", None) and r.user.is_authenticated
            else f"ip:{r.META.get('REMOTE_ADDR','')}",
        )
        limited = _rate_limit_or_429(request, rl)
        if limited:
            return limited

    if request.method == "POST" and is_owner:
        action = request.POST.get("action")

        if action in ("create", "draft"):
            form = PostCreateForm(request.POST)
            form.fields["collaborators"].queryset = _yaqin_users_for_collab(request.user)
            if form.is_valid():
                cd = form.cleaned_data
                is_draft = action == "draft"
                post_id = blog_storage.create_post(
                    user_id=request.user.id,
                    username=request.user.username,
                    title=cd["title"],
                    body=cd["body"],
                    mood=cd["mood"],
                    hashtag=cd.get("hashtag") or None,
                    parent_id=cd.get("parent") or None,
                    visibility=int(cd.get("visibility", blog_storage.VIS_PRIVATE)),
                    is_draft=is_draft,
                )
                if not is_draft:
                    allowed = set(_yaqin_users_for_collab(request.user).values_list("pk", flat=True))
                    cst = PostCollaboration.Status
                    for cu in cd.get("collaborators") or []:
                        if cu.pk not in allowed:
                            continue
                        pc_obj, created_collab = PostCollaboration.objects.get_or_create(
                            post_owner=request.user,
                            post_id=post_id,
                            collaborator=cu,
                            defaults={"status": cst.PENDING},
                        )
                        if created_collab:
                            try:
                                user_tasks.create_notification.delay(
                                    user_id=int(cu.pk),
                                    kind=str(Notification.Kind.COLLAB_INVITE),
                                    payload={
                                        "post_owner_id": request.user.id,
                                        "post_owner_username": request.user.username,
                                        "post_id": post_id,
                                        "collab_id": pc_obj.pk,
                                    },
                                )
                            except Exception:
                                Notification.objects.create(
                                    user=cu,
                                    kind=Notification.Kind.COLLAB_INVITE,
                                    payload={
                                        "post_owner_id": request.user.id,
                                        "post_owner_username": request.user.username,
                                        "post_id": post_id,
                                        "collab_id": pc_obj.pk,
                                    },
                                )

        elif action in ("update", "draft_update"):
            form = PostCreateForm(request.POST)
            form.fields["collaborators"].queryset = _yaqin_users_for_collab(request.user)
            pid = request.POST.get("post_id")
            if form.is_valid() and pid:
                cd = form.cleaned_data
                blog_storage.update_post(
                    user_id=request.user.id,
                    username=request.user.username,
                    post_id=int(pid),
                    title=cd["title"],
                    body=cd["body"],
                    mood=cd["mood"],
                    hashtag=cd.get("hashtag") or None,
                    visibility=int(cd.get("visibility", blog_storage.VIS_PRIVATE)),
                    is_draft=action == "draft_update",
                )

        elif action == "delete" and request.POST.get("post_id"):
            del_id = int(request.POST.get("post_id"))
            PostCollaboration.objects.filter(post_owner=request.user, post_id=del_id).delete()
            blog_storage.delete_post(
                user_id=request.user.id,
                username=request.user.username,
                post_id=del_id,
            )

        elif action == "toggle_status" and request.POST.get("post_id"):
            blog_storage.toggle_post_public(
                user_id=request.user.id,
                username=request.user.username,
                post_id=int(request.POST.get("post_id")),
            )

        return redirect("profile", username=username)

    if request.method == "POST" and request.user.is_authenticated and not is_owner:
        act = request.POST.get("action")
        st = YaqinRequest.Status
        if act == "yaqin_request" and request.user != profile_user:
            if not getattr(profile_user, "allow_yaqin_requests", True):
                messages.info(request, "Bu foydalanuvchi yaqin so‘rovlarini o‘chirgan.")
                return redirect("profile", username=username)
            if not _yaqin_accepted(request.user, profile_user):
                out = YaqinRequest.objects.filter(
                    from_user=request.user, to_user=profile_user, status=st.PENDING
                ).exists()
                inc = YaqinRequest.objects.filter(
                    from_user=profile_user, to_user=request.user, status=st.PENDING
                ).exists()
                if not out and not inc:
                    _yr, _created_req = YaqinRequest.objects.get_or_create(
                        from_user=request.user,
                        to_user=profile_user,
                        defaults={"status": st.PENDING},
                    )
                    if _yr.status == st.PENDING:
                        _ensure_yaqin_request_notification(
                            from_user=request.user, to_user=profile_user
                        )
        elif act == "yaqin_accept":
            YaqinRequest.objects.filter(
                from_user=profile_user, to_user=request.user, status=st.PENDING
            ).update(status=st.ACCEPTED)
        elif act == "yaqin_decline":
            YaqinRequest.objects.filter(
                from_user=profile_user, to_user=request.user, status=st.PENDING
            ).delete()
        elif act == "yaqin_cancel":
            YaqinRequest.objects.filter(
                from_user=request.user, to_user=profile_user, status=st.PENDING
            ).delete()
        return redirect("profile", username=username)

    query = request.GET.get("q")
    date_filter = request.GET.get("date")
    tag = request.GET.get("tag")
    try:
        cal_year = int(request.GET.get("cal_year", datetime.now().year))
        cal_month = int(request.GET.get("cal_month", datetime.now().month))
    except ValueError:
        cal_year, cal_month = datetime.now().year, datetime.now().month
    if cal_month < 1:
        cal_month, cal_year = 12, cal_year - 1
    if cal_month > 12:
        cal_month, cal_year = 1, cal_year + 1

    _, cal_last_day = calendar.monthrange(cal_year, cal_month)
    if cal_month == 1:
        cal_prev_year, cal_prev_month = cal_year - 1, 12
    else:
        cal_prev_year, cal_prev_month = cal_year, cal_month - 1
    if cal_month == 12:
        cal_next_year, cal_next_month = cal_year + 1, 1
    else:
        cal_next_year, cal_next_month = cal_year, cal_month + 1

    posts_list = blog_storage.list_posts(
        user_id=profile_user.id,
        username=profile_user.username,
        is_owner=is_owner,
        query=query,
        date_filter=date_filter,
        tag=tag,
        viewer_is_yaqin=viewer_is_yaqin,
    )

    if is_owner:
        collab_incoming: list = []
        cst = PostCollaboration.Status
        for pc in PostCollaboration.objects.filter(
            collaborator=profile_user, status=cst.ACCEPTED
        ).select_related("post_owner"):
            p = blog_storage.get_post(
                user_id=pc.post_owner_id,
                username=pc.post_owner.username,
                post_id=pc.post_id,
            )
            if not p or p.get("is_draft"):
                continue
            collab_incoming.append(
                {
                    **p,
                    "author_id": pc.post_owner_id,
                    "author_username": pc.post_owner.username,
                    "is_collab": True,
                }
            )
        posts_list = sorted(
            list(posts_list) + collab_incoming,
            key=lambda x: x["created_at"],
            reverse=True,
        )

    paginator = Paginator(posts_list, 10)
    page_number = request.GET.get("page", 1)
    posts = paginator.get_page(page_number)

    _hybrid_authors: dict[int, Optional[User]] = {profile_user.id: profile_user}
    _collab_decl = PostCollaboration.Status.DECLINED
    for _p in posts:
        _aid = int(_p["author_id"])
        if _aid not in _hybrid_authors:
            try:
                _hybrid_authors[_aid] = User.objects.get(pk=_aid)
            except User.DoesNotExist:
                _hybrid_authors[_aid] = None
        _au = _hybrid_authors[_aid]
        if _au:
            _p["feed_author_photo_url"] = _au.photo.url if _au.photo else ""
            _p["feed_author_initial"] = (_au.username[0] if _au.username else "?").upper()
            _p["feed_author_display"] = ((_au.get_full_name() or "").strip() or _au.username)
        else:
            _p["feed_author_photo_url"] = ""
            _p["feed_author_initial"] = "?"
            _p["feed_author_display"] = _p.get("author_username") or ""
        _pid = int(_p["id"])
        if is_owner:
            _p["collab_count"] = PostCollaboration.objects.filter(
                post_owner=profile_user, post_id=_pid
            ).exclude(status=_collab_decl).count()
        else:
            _p["collab_count"] = 0
        if _p.get("is_collab"):
            _p["collab_count"] = max(int(_p.get("collab_count") or 0), 1)

    cal_counts = blog_storage.calendar_day_counts(
        user_id=profile_user.id,
        username=profile_user.username,
        year=cal_year,
        month=cal_month,
    )
    cal_days = list(range(1, cal_last_day + 1))
    cal_cells = [{"d": d, "n": cal_counts.get(d, 0)} for d in cal_days]

    reminder_show = False
    if request.user.is_authenticated and request.user == profile_user and request.user.reminder_enabled:
        now = datetime.now()
        if now.weekday() == request.user.reminder_weekday and now.hour == request.user.reminder_hour:
            reminder_show = True

    yaqin_count = _yaqin_count(profile_user)
    yaqin_state = _yaqin_ui_state(request.user, profile_user)

    collab_by_post: dict = {}
    if is_owner:
        for c in PostCollaboration.objects.filter(post_owner=profile_user).select_related("collaborator"):
            collab_by_post.setdefault(c.post_id, []).append(c)

    context = {
        "profile_user": profile_user,
        "is_owner": is_owner,
        "viewer_is_yaqin": viewer_is_yaqin,
        "yaqin_count": yaqin_count,
        "yaqin_state": yaqin_state,
        "posts": posts,
        "query": query,
        "date_filter": date_filter,
        "tag": tag,
        "mood_label": blog_storage.mood_label,
        "cal_year": cal_year,
        "cal_month": cal_month,
        "cal_counts": cal_counts,
        "cal_last_day": cal_last_day,
        "cal_days": cal_days,
        "cal_cells": cal_cells,
        "cal_prev_year": cal_prev_year,
        "cal_prev_month": cal_prev_month,
        "cal_next_year": cal_next_year,
        "cal_next_month": cal_next_month,
        "reminder_show": reminder_show,
        "collab_by_post": collab_by_post,
        "incoming_yaqin_requests": _incoming_yaqin_pending(request.user)
        if (request.user.is_authenticated and is_owner)
        else [],
    }
    from blogs.forms import VISIBILITY_CHOICES

    context["visibility_labels"] = {v: lbl for v, lbl in VISIBILITY_CHOICES}
    k_active = Kayfiyat.objects.filter(is_active=True)
    context["kayfiyat_primary"] = list(k_active.filter(is_primary=True).order_by("sort_order", "name"))
    context["kayfiyat_extras"] = list(k_active.filter(is_primary=False).order_by("sort_order", "name"))
    context["default_mood_slug"] = (
        Kayfiyat.objects.filter(is_primary=True, is_active=True)
        .order_by("sort_order", "name")
        .values_list("slug", flat=True)
        .first()
        or ""
    )
    form = PostCreateForm()
    if request.user.is_authenticated and is_owner:
        form.fields["collaborators"].queryset = _yaqin_users_for_collab(request.user)
    context["form"] = form
    return render(request, "users/profile.html", context)


@login_required
def yaqin_list_view(request, username):
    """Profilga tegishli «yaqinlar» ro‘yxati (hamma ko‘ra oladi)."""
    profile_user = get_object_or_404(User, username=username)
    st = YaqinRequest.Status
    rels = list(
        YaqinRequest.objects.filter(
            Q(from_user=profile_user) | Q(to_user=profile_user),
            status=st.ACCEPTED,
        ).select_related("from_user", "to_user")
    )
    yaqin_ids: set[int] = set()
    for r in rels:
        if r.from_user_id == profile_user.id:
            yaqin_ids.add(int(r.to_user_id))
        else:
            yaqin_ids.add(int(r.from_user_id))
    yaqin_users = list(User.objects.filter(id__in=yaqin_ids).order_by("username"))
    return render(
        request,
        "users/yaqin_list.html",
        {"profile_user": profile_user, "yaqin_users": yaqin_users},
    )


def post_detail_view(request, username, post_id):
    profile_user = get_object_or_404(User, username=username)
    is_owner = request.user.is_authenticated and request.user == profile_user
    viewer_is_yaqin = _viewer_is_yaqin(request.user, profile_user)
    pid = int(post_id)
    post = blog_storage.get_post(user_id=profile_user.id, username=profile_user.username, post_id=pid)
    if not post:
        return render(
            request,
            "users/post_not_found.html",
            {"profile_user": profile_user},
            status=404,
        )
    visible = blog_storage.post_visible_to_viewer(post, is_owner=is_owner, viewer_is_yaqin=viewer_is_yaqin)
    cst = PostCollaboration.Status
    if not visible and request.user.is_authenticated:
        if PostCollaboration.objects.filter(
            post_owner=profile_user,
            post_id=pid,
            collaborator=request.user,
            status__in=[cst.PENDING, cst.ACCEPTED],
        ).exists():
            visible = True
    if not visible:
        return HttpResponseForbidden("Bu xotirani ko‘rish huquqingiz yo‘q.")

    can_comment = _viewer_can_comment(viewer=request.user, post_owner=profile_user)

    if request.method == "POST" and request.user.is_authenticated:
        if request.POST.get("action") == "add_comment":
            if not can_comment:
                return HttpResponseForbidden("Izoh qoldirish huquqingiz yo‘q.")
            body = (request.POST.get("body") or "").strip()
            if body:
                if len(body) > 500:
                    body = body[:500]
                Comment.objects.create(
                    post_owner=profile_user,
                    post_id=pid,
                    author=request.user,
                    body=body,
                )
                # Notify post owner via in-app + bot
                if request.user.pk != profile_user.pk:
                    try:
                        user_tasks.create_notification.delay(
                            user_id=int(profile_user.pk),
                            kind=str(Notification.Kind.COMMENT),
                            payload={
                                "from_username": request.user.username,
                                "post_owner_username": profile_user.username,
                                "post_id": int(pid),
                            },
                        )
                    except Exception:
                        Notification.objects.create(
                            user=profile_user,
                            kind=Notification.Kind.COMMENT,
                            payload={
                                "from_username": request.user.username,
                                "post_owner_username": profile_user.username,
                                "post_id": int(pid),
                            },
                        )
            return redirect("post_detail", username=username, post_id=pid)

    if request.user.is_authenticated:
        FeedPostSeen.objects.get_or_create(
            viewer=request.user,
            post_author=profile_user,
            post_id=pid,
        )

    comments = (
        Comment.objects.filter(post_owner=profile_user, post_id=pid)
        .select_related("author")
        .order_by("created_at")
    )
    collabs = PostCollaboration.objects.filter(post_owner=profile_user, post_id=pid).select_related(
        "collaborator"
    )
    from blogs.forms import VISIBILITY_CHOICES

    return render(
        request,
        "users/post_detail.html",
        {
            "profile_user": profile_user,
            "post": post,
            "is_owner": is_owner,
            "viewer_is_yaqin": viewer_is_yaqin,
            "can_comment": can_comment,
            "comments": comments,
            "post_collabs": collabs,
            "mood_label": blog_storage.mood_label,
            "visibility_labels": {v: lbl for v, lbl in VISIBILITY_CHOICES},
        },
    )


@login_required
def home_feed_view(request):
    ttl = _cache_ttl()
    page_num = request.GET.get("page", 1)

    # 1) yaqin ids cache (tez-tez o'zgarmaydi)
    yaqin_key = f"yaqin:ids:{request.user.pk}"
    yaqin_ids = cache.get(yaqin_key)
    if yaqin_ids is None:
        yaqin_ids = _yaqin_peer_ids(request.user)
        cache.set(yaqin_key, yaqin_ids, timeout=ttl)

    # 2) all_posts cache: per viewer + yaqin set (ko'p vaqtni SQLite feed list oladi)
    # Use stable short signature to keep cache keys small.
    yaqin_sig = hashlib.sha1(",".join(map(str, yaqin_ids)).encode("utf-8")).hexdigest()[:16]
    feed_key = f"feed:all:{request.user.pk}:{yaqin_sig}"
    all_posts = cache.get(feed_key)
    if all_posts is None:
        all_posts = []
        # bulk fetch usernames (avoid N+1)
        u_map = {
            int(u.pk): u
            for u in User.objects.filter(pk__in=yaqin_ids).only("id", "username")
        }
        for uid in yaqin_ids:
            u = u_map.get(int(uid))
            if not u:
                continue
            # cache per-author slice too (cheap for next viewers with same peer)
            ak = f"feed:author:{uid}"
            rows = cache.get(ak)
            if rows is None:
                rows = blog_storage.list_feed_posts_from_yaqin_author(
                    author_id=int(uid), author_username=u.username
                )
                cache.set(ak, rows, timeout=ttl)
            all_posts.extend(rows)
        all_posts.sort(key=lambda p: p["created_at"], reverse=True)
        cache.set(feed_key, all_posts, timeout=ttl)

    # 3) Seen pairs only for these authors (avoid scanning whole table)
    seen_pairs = set(
        FeedPostSeen.objects.filter(viewer=request.user, post_author_id__in=yaqin_ids).values_list(
            "post_author_id", "post_id"
        )
    )
    unseen = [p for p in all_posts if (int(p["author_id"]), int(p["id"])) not in seen_pairs]
    seen = [p for p in all_posts if (int(p["author_id"]), int(p["id"])) in seen_pairs]
    merged = unseen + seen

    paginator = Paginator(merged, 12)
    posts = paginator.get_page(page_num)

    # 4) Decorate only current page (avoid work for all merged posts)
    page_rows = list(posts.object_list)
    author_ids = sorted({int(p["author_id"]) for p in page_rows})
    authors = {
        int(u.pk): u
        for u in User.objects.filter(pk__in=author_ids).only("id", "username", "first_name", "last_name", "photo")
    }

    pairs = [(int(p["author_id"]), int(p["id"])) for p in page_rows]
    post_ids = sorted({pid for _aid, pid in pairs})
    collab_map: dict[tuple[int, int], int] = {}
    if author_ids and post_ids:
        collabs = (
            PostCollaboration.objects.filter(post_owner_id__in=author_ids, post_id__in=post_ids)
            .exclude(status=PostCollaboration.Status.DECLINED)
            .values("post_owner_id", "post_id")
            .annotate(cnt=Count("id"))
        )
        for c in collabs:
            collab_map[(int(c["post_owner_id"]), int(c["post_id"]))] = int(c["cnt"] or 0)

    for p in page_rows:
        aid = int(p["author_id"])
        pid = int(p["id"])
        u = authors.get(aid)
        p["feed_author_photo_url"] = u.photo.url if u and u.photo else ""
        p["feed_author_initial"] = (u.username[0] if u and u.username else "?").upper()
        p["feed_author_display"] = ((u.get_full_name() or "").strip() or u.username) if u else (p.get("author_username") or "")
        p["feed_seen_by_viewer"] = (aid, pid) in seen_pairs
        p["collab_count"] = int(collab_map.get((aid, pid), 0))
    posts.object_list = page_rows

    from blogs.forms import VISIBILITY_CHOICES

    # Instagram-uslubida: rekomendatsiya (accounts) — faqat yaqin bo‘lmaganlar.
    viewer_peers = set(yaqin_ids)
    viewer_region = getattr(request.user, "region", None)

    base_all = User.objects.filter(is_active=True).exclude(pk=request.user.pk)
    if viewer_peers:
        base_all = base_all.exclude(pk__in=viewer_peers)

    base_region = base_all
    if viewer_region:
        base_region = base_region.filter(region=viewer_region)

    # Region first, keyin umumiy bazadan to‘ldiramiz (har doim 20 ta).
    pool_region = list(
        base_region.only("id", "username", "first_name", "last_name", "photo", "region", "allow_yaqin_requests")
        .order_by("username")[:140]
    )
    region_ids = {u.pk for u in pool_region}
    pool_more = list(
        base_all.exclude(pk__in=list(region_ids))
        .only("id", "username", "first_name", "last_name", "photo", "region", "allow_yaqin_requests")
        .order_by("username")[:220]
    )
    pool = (pool_region + pool_more)[:220]
    pool_ids = [u.pk for u in pool]

    # viewer <-> candidate status (pending/accepted)
    rels = list(
        YaqinRequest.objects.filter(
            Q(from_user=request.user, to_user_id__in=pool_ids)
            | Q(to_user=request.user, from_user_id__in=pool_ids)
        ).only("from_user_id", "to_user_id", "status")
    )
    pending_out = set()
    pending_in = set()
    accepted = set()
    for r in rels:
        if r.status == YaqinRequest.Status.ACCEPTED:
            other = r.to_user_id if r.from_user_id == request.user.pk else r.from_user_id
            accepted.add(int(other))
        elif r.status == YaqinRequest.Status.PENDING:
            if r.from_user_id == request.user.pk:
                pending_out.add(int(r.to_user_id))
            elif r.to_user_id == request.user.pk:
                pending_in.add(int(r.from_user_id))

    # mutual counts: candidate <-> viewer peers (accepted only)
    mutual_map: dict[int, int] = {int(pid): 0 for pid in pool_ids}
    if viewer_peers and pool_ids:
        mrels = list(
            YaqinRequest.objects.filter(status=YaqinRequest.Status.ACCEPTED)
            .filter(
                (Q(from_user_id__in=pool_ids) & Q(to_user_id__in=viewer_peers))
                | (Q(to_user_id__in=pool_ids) & Q(from_user_id__in=viewer_peers))
            )
            .only("from_user_id", "to_user_id")
        )
        for r in mrels:
            if r.from_user_id in viewer_peers and r.to_user_id in mutual_map:
                mutual_map[int(r.to_user_id)] = mutual_map.get(int(r.to_user_id), 0) + 1
            elif r.to_user_id in viewer_peers and r.from_user_id in mutual_map:
                mutual_map[int(r.from_user_id)] = mutual_map.get(int(r.from_user_id), 0) + 1

    reco_rows: list[dict] = []
    for u in pool:
        uid = int(u.pk)
        # bu viewda yaqin bo‘lmaganlar bo‘lishi kerak
        if uid in accepted:
            continue
        if uid in pending_out:
            state = "pending_out"
        elif uid in pending_in:
            state = "pending_in"
        else:
            state = "none"
        reco_rows.append(
            {
                "user": u,
                "display": (u.get_full_name() or "").strip() or u.username,
                "state": state,
                "mutual": int(mutual_map.get(uid, 0) or 0),
                "allow_requests": bool(getattr(u, "allow_yaqin_requests", True)),
            }
        )
    reco_rows.sort(key=lambda r: (r["mutual"], r["user"].username), reverse=True)
    reco_rows = reco_rows[:20]

    return render(
        request,
        "feed.html",
        {
            "posts": posts,
            "reco_rows": reco_rows,
            "visibility_labels": {v: lbl for v, lbl in VISIBILITY_CHOICES},
            "incoming_yaqin_requests": _incoming_yaqin_pending(request.user),
        },
    )


def service_worker_js(request):
    """Brauzer /sw.js so‘raganda 404 chiqmasin (minimal javob)."""
    return HttpResponse(
        "// MYFEEL: service worker ishlatilmaydi.\n",
        content_type="application/javascript; charset=utf-8",
    )


@login_required
@require_POST
@ratelimit(RateLimit("yaqin_action", limit=40, window_seconds=60, key_func=lambda r: f"u:{r.user.pk}"))
def yaqin_action_view(request):
    """
    Yaqinlik uchun tezkor action (feed/recommendation/search va boshqalardan).
    POST: action, username, next (ixtiyoriy).
    """
    act = (request.POST.get("action") or "").strip()
    uname = (request.POST.get("username") or "").strip()
    nxt = (request.POST.get("next") or "").strip()

    target = User.objects.filter(username=uname, is_active=True).first()
    if not target or target.pk == request.user.pk:
        return redirect("home_feed")

    st = YaqinRequest.Status
    if act == "yaqin_request":
        if not getattr(target, "allow_yaqin_requests", True):
            messages.info(request, "Bu foydalanuvchi yaqin so‘rovlarini o‘chirgan.")
        elif not _yaqin_accepted(request.user, target):
            out = YaqinRequest.objects.filter(
                from_user=request.user, to_user=target, status=st.PENDING
            ).exists()
            inc = YaqinRequest.objects.filter(
                from_user=target, to_user=request.user, status=st.PENDING
            ).exists()
            if not out and not inc:
                yr, _created_req = YaqinRequest.objects.get_or_create(
                    from_user=request.user,
                    to_user=target,
                    defaults={"status": st.PENDING},
                )
                if yr.status == st.PENDING:
                    _ensure_yaqin_request_notification(from_user=request.user, to_user=target)
    elif act == "yaqin_accept":
        YaqinRequest.objects.filter(
            from_user=target, to_user=request.user, status=st.PENDING
        ).update(status=st.ACCEPTED)
    elif act == "yaqin_decline":
        YaqinRequest.objects.filter(
            from_user=target, to_user=request.user, status=st.PENDING
        ).delete()
    elif act == "yaqin_cancel":
        YaqinRequest.objects.filter(
            from_user=request.user, to_user=target, status=st.PENDING
        ).delete()

    if nxt.startswith("/"):
        return redirect(nxt)
    return redirect("home_feed")


@login_required
@require_POST
def mark_feed_post_seen_view(request):
    try:
        aid = int(request.POST.get("post_author_id", "0"))
        pid = int(request.POST.get("post_id", "0"))
    except ValueError:
        return redirect("home_feed")
    FeedPostSeen.objects.get_or_create(
        viewer=request.user,
        post_author_id=aid,
        post_id=pid,
    )
    if request.headers.get("HX-Request") == "true":
        return render(
            request,
            "includes/feed_seen_done.html",
            {"post_author_id": aid, "post_id": pid},
        )
    nxt = request.POST.get("next") or ""
    if nxt.startswith("/"):
        return redirect(nxt)
    return redirect("home_feed")


@login_required
@require_POST
@ratelimit(RateLimit("feed_hx", limit=120, window_seconds=60, key_func=lambda r: f"u:{r.user.pk}"))
def feed_hx_interaction_view(request):
    """HTMX: lenta postidagi yengil o‘zaro ta’sir (yoqtirish / repost stub)."""
    if request.headers.get("HX-Request") != "true":
        return HttpResponse(status=400)
    kind = (request.POST.get("kind") or "").strip()
    if kind == "like":
        return render(request, "includes/hx_like_icon.html")
    return HttpResponse(status=204)


@login_required
def notifications_view(request):
    if request.method == "POST":
        act = request.POST.get("action")
        if act == "mark_all_read":
            Notification.objects.filter(user=request.user, read_at__isnull=True).update(
                read_at=timezone.now()
            )
        elif act == "collab_accept":
            pc = _find_pending_collaboration(
                request.user,
                collab_id_raw=request.POST.get("collab_id"),
                post_owner_username=request.POST.get("post_owner_username"),
                post_id_raw=request.POST.get("post_id"),
            )
            if pc:
                pc.status = PostCollaboration.Status.ACCEPTED
                pc.save(update_fields=["status", "updated_at"])
                messages.success(request, "Hammualliflik qabul qilindi — post endi profilingizda ham ko‘rinadi.")
            else:
                messages.warning(
                    request,
                    "Bu taklif topilmadi yoki muddati o‘tgan (post o‘chirilgan yoki javob allaqachon berilgan).",
                )
        elif act == "collab_decline":
            pc = _find_pending_collaboration(
                request.user,
                collab_id_raw=request.POST.get("collab_id"),
                post_owner_username=request.POST.get("post_owner_username"),
                post_id_raw=request.POST.get("post_id"),
            )
            if pc:
                pc.status = PostCollaboration.Status.DECLINED
                pc.save(update_fields=["status", "updated_at"])
                messages.info(request, "Hammualliflik taklifi rad etildi.")
            else:
                messages.warning(request, "Bu taklifni rad etib bo‘lmaydi — allaqachon yopilgan.")
        return redirect("activity")

    items = list(Notification.objects.filter(user=request.user).order_by("-created_at")[:100])
    nk = Notification.Kind
    usernames: set[str] = set()
    for n in items:
        pl = n.payload or {}
        if n.kind == nk.YAQIN_REQUEST:
            u = pl.get("from_username")
            if isinstance(u, str) and u.strip():
                usernames.add(u.strip())
        elif n.kind == nk.COLLAB_INVITE:
            u = pl.get("post_owner_username")
            if isinstance(u, str) and u.strip():
                usernames.add(u.strip())
        elif n.kind == nk.DM_MESSAGE:
            u = pl.get("from_username")
            if isinstance(u, str) and u.strip():
                usernames.add(u.strip())
    user_map = {u.username: u for u in User.objects.filter(username__in=usernames)}
    activity_rows: list[dict] = []
    for n in items:
        pl = n.payload or {}
        actor = None
        if n.kind == nk.YAQIN_REQUEST:
            actor = user_map.get((pl.get("from_username") or "").strip())
        elif n.kind == nk.COLLAB_INVITE:
            actor = user_map.get((pl.get("post_owner_username") or "").strip())
        elif n.kind == nk.DM_MESSAGE:
            actor = user_map.get((pl.get("from_username") or "").strip())
        activity_rows.append({"notification": n, "actor": actor})

    # Sahifani ochganda barchasini o‘qilgan deb belgilash (badge tozalanadi)
    now = timezone.now()
    Notification.objects.filter(user=request.user, read_at__isnull=True).update(read_at=now)
    for n in items:
        if n.read_at is None:
            n.read_at = now

    return render(
        request,
        "users/activity.html",
        {"activity_rows": activity_rows},
    )


@login_required
def hashtag_explore_view(request, tag):
    raw = blog_storage.search_hashtag_global(tag)
    enriched = []
    for row in raw:
        uid = row.get("author_id")
        try:
            u = User.objects.get(pk=uid)
            row = {**row, "author_username": u.username}
            enriched.append(row)
        except User.DoesNotExist:
            continue
    return render(
        request,
        "users/hashtag_explore.html",
        {"tag": tag.strip().lstrip("#"), "posts": enriched[:60]},
    )


@login_required
def recap_view(request, username):
    profile_user = get_object_or_404(User, username=username)
    is_owner = request.user == profile_user
    if not is_owner:
        return HttpResponseForbidden()
    try:
        year = int(request.GET.get("year", datetime.now().year))
    except ValueError:
        year = datetime.now().year
    stats = blog_storage.recap_for_year(user_id=profile_user.id, username=profile_user.username, year=year)
    return render(
        request,
        "users/recap.html",
        {"profile_user": profile_user, "stats": stats, "year": year},
    )


@login_required
def recap_export_txt(request, username):
    profile_user = get_object_or_404(User, username=username)
    if request.user != profile_user:
        return HttpResponseForbidden()
    try:
        year = int(request.GET.get("year", datetime.now().year))
    except ValueError:
        year = datetime.now().year
    lines = blog_storage.export_posts_text_lines(
        user_id=profile_user.id, username=profile_user.username, year=year
    )
    body = "\n".join(lines) or "(Bo‘sh)"
    resp = HttpResponse(body, content_type="text/plain; charset=utf-8")
    resp["Content-Disposition"] = f'attachment; filename="myfeel-{username}-{year}.txt"'
    return resp


@login_required
def profile_edit_view(request):
    if request.method == "POST":
        user = request.user

        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.bio = request.POST.get("bio", user.bio)
        user.gender = request.POST.get("gender", user.gender)
        user.dob = request.POST.get("dob") or user.dob
        user.region = request.POST.get("region", user.region)

        link1 = request.POST.get("link1", "").strip()
        link2 = request.POST.get("link2", "").strip()
        link3 = request.POST.get("link3", "").strip()

        links = []
        if link1:
            links.append(link1)
        if link2:
            links.append(link2)
        if link3:
            links.append(link3)
        user.links = links

        if "photo" in request.FILES:
            upload = request.FILES["photo"]
            # Windows/dev muhitlarda ba'zan FileField assign qilinsa ham storage'ga yozilmay qolishi mumkin.
            # photo.save(...) storage'ga yozishni majburlaydi.
            user.photo.save(upload.name, upload, save=False)

        user.save()
        return redirect("profile", username=user.username)

    return render(request, "users/edit_profile.html", {"regions": Region.choices})


@login_required
def profile_settings_view(request):
    if request.method == "POST":
        user = request.user
        new_username = request.POST.get("new_username")
        new_password = request.POST.get("new_password")

        # Yangi bo‘limlar (Instagram-uslubida)
        if request.POST.get("settings_section") == "prefs":
            try:
                dv = int(request.POST.get("default_post_visibility", user.default_post_visibility))
                user.default_post_visibility = max(0, min(3, dv))
            except ValueError:
                pass
            user.compose_autosave_enabled = request.POST.get("compose_autosave_enabled") == "on"
            user.allow_yaqin_requests = request.POST.get("allow_yaqin_requests") == "on"
            user.allow_collab_invites = request.POST.get("allow_collab_invites") == "on"
            user.save(
                update_fields=[
                    "default_post_visibility",
                    "compose_autosave_enabled",
                    "allow_yaqin_requests",
                    "allow_collab_invites",
                ]
            )
            return redirect("profile_settings")

        if "reminder_enabled" in request.POST:
            user.reminder_enabled = request.POST.get("reminder_enabled") == "on"
            try:
                user.reminder_weekday = int(request.POST.get("reminder_weekday", user.reminder_weekday))
            except ValueError:
                pass
            try:
                h = int(request.POST.get("reminder_hour", user.reminder_hour))
                user.reminder_hour = max(0, min(23, h))
            except ValueError:
                pass
            user.save(update_fields=["reminder_enabled", "reminder_weekday", "reminder_hour"])
            return redirect("profile_settings")

        changed = False
        if new_username and new_username != user.username:
            user.username = new_username
            changed = True

        if new_password:
            user.set_password(new_password)
            changed = True

        if changed:
            user.save()
            from django.contrib.auth import update_session_auth_hash

            update_session_auth_hash(request, user)

        return redirect("profile", username=user.username)

    return render(request, "users/settings.html")


def logout_view(request):
    logout(request)
    return redirect("login")
