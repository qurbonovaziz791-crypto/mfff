from __future__ import annotations

from datetime import datetime
from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone
from ninja import Router, Schema

from api.auth import MobileOrSessionAuth
from blogs import storage as blog_storage
from blogs.models import Kayfiyat
from users.models import FeedPostSeen, PostCollaboration, YaqinRequest

User = get_user_model()

router = Router(tags=["mobile", "feed"])
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


def _mood_emoji(slug: str) -> str:
    s = (slug or "").strip()
    if not s:
        return ""
    k = Kayfiyat.objects.filter(slug=s).first()
    if k and (k.emoji or "").strip():
        return (k.emoji or "").strip()
    lbl = blog_storage.mood_label(s)
    return (lbl or "")[:2]


def _yaqin_peer_ids(user: User) -> list[int]:
    rows = list(
        YaqinRequest.objects.filter(status=YaqinRequest.Status.ACCEPTED)
        .filter(Q(from_user=user) | Q(to_user=user))
        .values_list("from_user_id", "to_user_id")
    )
    out: list[int] = []
    for a, b in rows:
        other = int(b) if int(a) == int(user.pk) else int(a)
        out.append(other)
    return out


class FeedPostOut(Schema):
    id: int
    author_id: int
    author_username: str
    author_display: str = ""
    author_photo_url: str = ""
    author_initial: str = ""
    title: str
    body: str
    hashtag: str = ""
    mood: str
    mood_emoji: str = ""
    created_at: str
    visibility: int = 0
    is_draft: bool = False
    collab_count: int = 0
    seen_by_viewer: bool = False


class FeedOut(Schema):
    page: int
    page_size: int
    has_next: bool
    posts: list[FeedPostOut]


@router.get("/", auth=auth, response=FeedOut)
def feed_list(request, page: int = 1, page_size: int = 12):
    viewer: User = request.auth
    yaqin_ids = _yaqin_peer_ids(viewer)

    # gather posts from yaqin authors
    all_posts: list[dict] = []
    authors = {u.pk: u for u in User.objects.filter(pk__in=yaqin_ids).only("id", "username", "first_name", "last_name", "photo")}
    for uid in yaqin_ids:
        u = authors.get(uid)
        if not u:
            continue
        all_posts.extend(
            blog_storage.list_feed_posts_from_yaqin_author(author_id=int(uid), author_username=u.username)
        )

    all_posts.sort(key=lambda p: p["created_at"], reverse=True)

    seen_pairs = set(
        FeedPostSeen.objects.filter(viewer=viewer).values_list("post_author_id", "post_id")
    )
    unseen = [p for p in all_posts if (p["author_id"], p["id"]) not in seen_pairs]
    seen = [p for p in all_posts if (p["author_id"], p["id"]) in seen_pairs]
    merged = unseen + seen

    p = max(1, int(page or 1))
    ps = max(1, min(50, int(page_size or 12)))
    start = (p - 1) * ps
    end = start + ps
    chunk = merged[start:end]
    has_next = end < len(merged)

    out: list[FeedPostOut] = []
    for row in chunk:
        aid = int(row["author_id"])
        pid = int(row["id"])
        au = authors.get(aid) or User.objects.filter(pk=aid).only("id", "username", "first_name", "last_name", "photo").first()
        uname = (au.username if au else row.get("author_username") or "") if au else (row.get("author_username") or "")
        photo = _abs_media_url(request, _photo_url(au)) if au else ""
        created = row["created_at"].isoformat() if hasattr(row.get("created_at"), "isoformat") else str(row.get("created_at"))
        out.append(
            FeedPostOut(
                id=pid,
                author_id=aid,
                author_username=str(uname),
                author_display=_display_name(au) if au else str(uname),
                author_photo_url=photo,
                author_initial=((str(uname)[:1] or "?").upper()),
                title=str(row.get("title") or ""),
                body=str(row.get("body") or ""),
                hashtag=str(row.get("hashtag") or ""),
                mood=str(row.get("mood") or ""),
                mood_emoji=_mood_emoji(str(row.get("mood") or "")),
                created_at=created,
                visibility=int(row.get("visibility") or 0),
                is_draft=bool(row.get("is_draft")),
                collab_count=int(
                    PostCollaboration.objects.filter(post_owner_id=aid, post_id=pid)
                    .exclude(status=PostCollaboration.Status.DECLINED)
                    .count()
                ),
                seen_by_viewer=(aid, pid) in seen_pairs,
            )
        )

    return FeedOut(page=p, page_size=ps, has_next=bool(has_next), posts=out)


class MarkSeenIn(Schema):
    post_author_id: int
    post_id: int


@router.post("/mark-seen", auth=auth, response={200: dict})
def mark_seen(request, payload: MarkSeenIn):
    viewer: User = request.auth
    aid = int(payload.post_author_id)
    pid = int(payload.post_id)
    FeedPostSeen.objects.get_or_create(viewer=viewer, post_author_id=aid, post_id=pid)
    return {"ok": True, "seen_at": timezone.now().isoformat()}

