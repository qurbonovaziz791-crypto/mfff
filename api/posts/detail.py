from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Q
from ninja import Router, Schema

from blogs import storage as blog_storage
from users.models import Comment, PostCollaboration, YaqinRequest

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


def _viewer_can_comment(*, viewer: Optional[User], post_owner: User) -> bool:
    if not viewer or not getattr(viewer, "is_authenticated", False):
        return False
    if viewer.pk == post_owner.pk:
        return True
    return _viewer_is_yaqin(viewer=viewer, profile_user=post_owner)


class CommentAuthorOut(Schema):
    id: int
    username: str
    display: str = ""
    photo_url: str = ""
    initial: str = ""


class CommentOut(Schema):
    id: int
    body: str
    created_at: str
    author: CommentAuthorOut


class PostDetailOut(Schema):
    ok: bool = True
    post: dict
    comments: list[CommentOut]
    can_comment: bool = False


class CommentCreateIn(Schema):
    body: str


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


@router.get("/detail/{username}/{post_id}", auth=auth, response={200: PostDetailOut, 403: dict, 404: dict})
def post_detail(request, username: str, post_id: int):
    owner = User.objects.filter(username=username, is_active=True).first()
    if not owner:
        return 404, {"ok": False, "detail": "Not found"}

    viewer: User = request.auth
    is_owner = bool(viewer and viewer.is_authenticated and viewer.pk == owner.pk)
    viewer_is_yaqin = _viewer_is_yaqin(viewer=viewer, profile_user=owner)

    pid = int(post_id)
    post = blog_storage.get_post(user_id=owner.id, username=owner.username, post_id=pid)
    if not post:
        return 404, {"ok": False, "detail": "Not found"}

    visible = blog_storage.post_visible_to_viewer(post, is_owner=is_owner, viewer_is_yaqin=viewer_is_yaqin)
    if not visible and viewer and getattr(viewer, "is_authenticated", False):
        cst = PostCollaboration.Status
        if PostCollaboration.objects.filter(
            post_owner=owner,
            post_id=pid,
            collaborator=viewer,
            status__in=[cst.PENDING, cst.ACCEPTED],
        ).exists():
            visible = True
    if not visible:
        return 403, {"ok": False, "detail": "Forbidden"}

    can_comment = _viewer_can_comment(viewer=viewer, post_owner=owner)

    # shape for mobile client (same keys as list endpoints expect + extra author info)
    post_out = {
        **post,
        "author_id": int(owner.id),
        "author_username": str(owner.username),
        "author_display": _display_name(owner),
        "author_photo_url": _abs_media_url(request, _photo_url(owner)),
        "author_initial": ((str(owner.username or "?")[:1]).upper()),
        "created_at": post["created_at"].isoformat() if getattr(post.get("created_at"), "isoformat", None) else str(post.get("created_at")),
        "mood_emoji": blog_storage.mood_label(str(post.get("mood") or ""))[:2],
    }

    comments_qs = Comment.objects.filter(post_owner=owner, post_id=pid).select_related("author").order_by("created_at")[:200]
    cm_out: list[CommentOut] = []
    for c in comments_qs:
        au = c.author
        uname = str(getattr(au, "username", "") or "")
        cm_out.append(
            CommentOut(
                id=int(c.id),
                body=str(c.body or ""),
                created_at=c.created_at.isoformat(),
                author=CommentAuthorOut(
                    id=int(au.id),
                    username=uname,
                    display=_display_name(au),
                    photo_url=_abs_media_url(request, _photo_url(au)),
                    initial=((uname[:1] or "?").upper()),
                ),
            )
        )

    return PostDetailOut(post=post_out, comments=cm_out, can_comment=bool(can_comment))


@router.post("/detail/{username}/{post_id}/comment", auth=auth, response={200: PostDetailOut, 400: dict, 403: dict, 404: dict})
def post_add_comment(request, username: str, post_id: int, payload: CommentCreateIn):
    owner = User.objects.filter(username=username, is_active=True).first()
    if not owner:
        return 404, {"ok": False, "detail": "Not found"}

    viewer: User = request.auth
    if not _viewer_can_comment(viewer=viewer, post_owner=owner):
        return 403, {"ok": False, "detail": "Forbidden"}

    pid = int(post_id)
    post = blog_storage.get_post(user_id=owner.id, username=owner.username, post_id=pid)
    if not post:
        return 404, {"ok": False, "detail": "Not found"}

    body = (payload.body or "").strip()
    if not body:
        return 400, {"ok": False, "detail": "Body is required"}
    if len(body) > 500:
        body = body[:500]
    Comment.objects.create(post_owner=owner, post_id=pid, author=viewer, body=body)

    # return fresh detail (cheap enough for now)
    return post_detail(request, username=username, post_id=pid)

