from __future__ import annotations

from typing import Optional

from django.db.models import Q
from django.contrib.auth import get_user_model
from ninja import Router, Schema

from blogs import storage as blog_storage
from blogs.models import Kayfiyat
from users.models import PostCollaboration, YaqinRequest

from api.auth import MobileOrSessionAuth

User = get_user_model()

router = Router(tags=["mobile", "posts"])
auth = MobileOrSessionAuth()


def _viewer_is_yaqin(*, viewer: Optional[User], profile_user: User) -> bool:
    if not viewer or not getattr(viewer, "is_authenticated", False):
        return False
    if viewer.pk == profile_user.pk:
        return False
    return YaqinRequest.objects.filter(status=YaqinRequest.Status.ACCEPTED).filter(
        (Q(from_user=viewer) & Q(to_user=profile_user)) | (Q(from_user=profile_user) & Q(to_user=viewer))
    ).exists()


def _yaqin_count(user: User) -> int:
    return (
        YaqinRequest.objects.filter(status=YaqinRequest.Status.ACCEPTED)
        .filter(from_user=user)
        .count()
        + YaqinRequest.objects.filter(status=YaqinRequest.Status.ACCEPTED)
        .filter(to_user=user)
        .count()
    )


def _mood_emoji(slug: str) -> str:
    s = (slug or "").strip()
    if not s:
        return ""
    k = Kayfiyat.objects.filter(slug=s).first()
    if k and (k.emoji or "").strip():
        return (k.emoji or "").strip()
    lbl = blog_storage.mood_label(s)
    return (lbl or "")[:2]


def _photo_url(u: User) -> str:
    try:
        if getattr(u, "photo", None) and u.photo:
            return u.photo.url
    except Exception:
        return ""
    return ""


def _abs_media_url(request, maybe_path: str) -> str:
    """
    Convert Django media relative path (/media/...) to absolute URL for mobile/web clients.
    """
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
    # unexpected, but keep as-is
    return raw


def _display_name(u: User) -> str:
    nm = (u.get_full_name() or "").strip()
    return nm or (u.username or "")


class ProfileOut(Schema):
    id: int
    username: str
    first_name: str = ""
    last_name: str = ""
    is_verified: bool = False
    bio: str = ""
    region: Optional[str] = None
    photo_url: str = ""
    display_name: str = ""

    posts_count: int = 0
    yaqin_count: int = 0


class PostOut(Schema):
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
    is_public: bool = False
    is_draft: bool = False
    collab_count: int = 0


class ProfileWithPostsOut(Schema):
    profile: ProfileOut
    page: int
    page_size: int
    has_next: bool
    posts: list[PostOut]


def _paginate(items: list[dict], *, page: int, page_size: int) -> tuple[list[dict], bool]:
    p = max(1, int(page or 1))
    ps = max(1, min(50, int(page_size or 10)))
    start = (p - 1) * ps
    end = start + ps
    chunk = items[start:end]
    has_next = end < len(items)
    return chunk, has_next


@router.get("/me", auth=auth, response=ProfileWithPostsOut)
def me_profile_posts(request, page: int = 1, page_size: int = 10):
    me: User = request.auth
    raw = list(
        blog_storage.list_posts(
            user_id=me.id,
            username=me.username,
            is_owner=True,
            viewer_is_yaqin=True,
        )
    )
    posts_count = len(raw)
    chunk, has_next = _paginate(raw, page=page, page_size=page_size)

    me_photo = _abs_media_url(request, _photo_url(me))
    p_out: list[PostOut] = []
    for d in chunk:
        created = d["created_at"].isoformat() if getattr(d.get("created_at"), "isoformat", None) else str(d.get("created_at"))
        username = me.username or ""
        p_out.append(
            PostOut(
                id=int(d["id"]),
                author_id=int(me.id),
                author_username=username,
                author_display=_display_name(me),
                author_photo_url=me_photo,
                author_initial=((username[:1] or "?").upper()),
                title=str(d.get("title") or ""),
                body=str(d.get("body") or ""),
                hashtag=str(d.get("hashtag") or ""),
                mood=str(d.get("mood") or ""),
                mood_emoji=_mood_emoji(str(d.get("mood") or "")),
                created_at=created,
                visibility=int(d.get("visibility") or 0),
                is_public=bool(d.get("is_public")),
                is_draft=bool(d.get("is_draft")),
                collab_count=int(
                    PostCollaboration.objects.filter(post_owner=me, post_id=int(d["id"]))
                    .exclude(status=PostCollaboration.Status.DECLINED)
                    .count()
                ),
            )
        )

    return ProfileWithPostsOut(
        profile=ProfileOut(
            id=int(me.id),
            username=str(me.username),
            first_name=str(getattr(me, "first_name", "") or ""),
            last_name=str(getattr(me, "last_name", "") or ""),
            is_verified=bool(getattr(me, "is_verified", False)),
            bio=str(getattr(me, "bio", "") or ""),
            region=str(getattr(me, "region", "") or "") or None,
            photo_url=me_photo,
            display_name=_display_name(me),
            posts_count=int(posts_count),
            yaqin_count=int(_yaqin_count(me)),
        ),
        page=max(1, int(page or 1)),
        page_size=max(1, min(50, int(page_size or 10))),
        has_next=bool(has_next),
        posts=p_out,
    )


@router.get("/profile/{username}", auth=auth, response=ProfileWithPostsOut)
def profile_posts(request, username: str, page: int = 1, page_size: int = 10):
    viewer: User = request.auth
    u = User.objects.filter(username=username, is_active=True).first()
    if not u:
        # Ninja will serialize this as 200 unless we raise; keep simple:
        return ProfileWithPostsOut(profile=ProfileOut(id=0, username=""), page=1, page_size=page_size, has_next=False, posts=[])

    is_owner = viewer.pk == u.pk
    viewer_is_yaqin = _viewer_is_yaqin(viewer=viewer, profile_user=u)

    raw = list(
        blog_storage.list_posts(
            user_id=u.id,
            username=u.username,
            is_owner=is_owner,
            viewer_is_yaqin=viewer_is_yaqin,
            include_drafts=is_owner,
        )
    )
    posts_count = len(raw)
    chunk, has_next = _paginate(raw, page=page, page_size=page_size)

    u_photo = _abs_media_url(request, _photo_url(u))
    p_out: list[PostOut] = []
    for d in chunk:
        created = d["created_at"].isoformat() if getattr(d.get("created_at"), "isoformat", None) else str(d.get("created_at"))
        uname = u.username or ""
        p_out.append(
            PostOut(
                id=int(d["id"]),
                author_id=int(u.id),
                author_username=uname,
                author_display=_display_name(u),
                author_photo_url=u_photo,
                author_initial=((uname[:1] or "?").upper()),
                title=str(d.get("title") or ""),
                body=str(d.get("body") or ""),
                hashtag=str(d.get("hashtag") or ""),
                mood=str(d.get("mood") or ""),
                mood_emoji=_mood_emoji(str(d.get("mood") or "")),
                created_at=created,
                visibility=int(d.get("visibility") or 0),
                is_public=bool(d.get("is_public")),
                is_draft=bool(d.get("is_draft")),
                collab_count=0,
            )
        )

    return ProfileWithPostsOut(
        profile=ProfileOut(
            id=int(u.id),
            username=str(u.username),
            first_name=str(getattr(u, "first_name", "") or ""),
            last_name=str(getattr(u, "last_name", "") or ""),
            is_verified=bool(getattr(u, "is_verified", False)),
            bio=str(getattr(u, "bio", "") or ""),
            region=str(getattr(u, "region", "") or "") or None,
            photo_url=u_photo,
            display_name=_display_name(u),
            posts_count=int(posts_count),
            yaqin_count=int(_yaqin_count(u)),
        ),
        page=max(1, int(page or 1)),
        page_size=max(1, min(50, int(page_size or 10))),
        has_next=bool(has_next),
        posts=p_out,
    )

