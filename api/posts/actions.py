from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Q
from ninja import Router, Schema

from api.auth import MobileOrSessionAuth
from blogs import storage as blog_storage
from blogs.models import Kayfiyat
from users.models import Notification, PostCollaboration, YaqinRequest

User = get_user_model()

router = Router(tags=["mobile", "posts"])
auth = MobileOrSessionAuth()


class MoodOut(Schema):
    slug: str
    name: str
    emoji: str = ""
    is_primary: bool = False


@router.get("/moods", auth=auth, response=list[MoodOut])
def moods(request):
    rows = list(Kayfiyat.objects.filter(is_active=True).order_by("-is_primary", "sort_order", "name"))
    return [
        MoodOut(slug=str(k.slug), name=str(k.name), emoji=str(k.emoji or ""), is_primary=bool(k.is_primary))
        for k in rows
    ]


class PostCreateIn(Schema):
    title: str
    body: str
    hashtag: Optional[str] = None
    mood: Optional[str] = None
    visibility: int = 0
    is_draft: bool = False
    collaborators: list[str] = []  # usernames (max 2)


@router.post("/create", auth=auth, response={200: dict, 400: dict})
def create_post_api(request, payload: PostCreateIn):
    me: User = request.auth
    title = (payload.title or "").strip()
    body = (payload.body or "").strip()
    if not title or not body:
        return 400, {"ok": False, "detail": "title/body required"}
    if len(title) > 50:
        title = title[:50]
    if len(body) > 255:
        body = body[:255]
    hashtag = (payload.hashtag or "").strip()
    if hashtag and not hashtag.startswith("#"):
        hashtag = f"#{hashtag}"
    mood = (payload.mood or "").strip()
    if mood and not Kayfiyat.objects.filter(slug=mood, is_active=True).exists():
        mood = ""
    if not mood:
        mood = (
            Kayfiyat.objects.filter(is_primary=True, is_active=True)
            .order_by("sort_order", "name")
            .values_list("slug", flat=True)
            .first()
            or "quvnoq"
        )
    vis = int(payload.visibility or 0)
    vis = max(0, min(3, vis))
    pid = blog_storage.create_post(
        user_id=me.id,
        username=me.username,
        title=title,
        body=body,
        mood=mood,
        hashtag=hashtag or None,
        visibility=vis,
        is_draft=bool(payload.is_draft),
    )

    # optional: add up to 2 collaborators (yaqin only)
    try:
        raw = payload.collaborators or []
    except Exception:
        raw = []
    collabs = [str(x).strip().lstrip("@") for x in raw if str(x).strip()]
    # unique + keep order
    seen = set()
    collabs_u: list[str] = []
    for u in collabs:
        if not u or u == me.username:
            continue
        if u in seen:
            continue
        seen.add(u)
        collabs_u.append(u)
    collabs_u = collabs_u[:2]

    if collabs_u and not bool(payload.is_draft):
        st = YaqinRequest.Status
        yaqin_ids = set(
            YaqinRequest.objects.filter(status=st.ACCEPTED)
            .filter(Q(from_user=me) | Q(to_user=me))
            .values_list("from_user_id", "to_user_id")
        )
        allowed: set[int] = set()
        for a, b in yaqin_ids:
            allowed.add(int(b) if int(a) == int(me.pk) else int(a))
        cands = list(User.objects.filter(username__in=collabs_u, is_active=True).only("id", "username", "allow_collab_invites"))
        for cu in cands:
            if int(cu.pk) not in allowed:
                continue
            if not getattr(cu, "allow_collab_invites", True):
                continue
            pc, created = PostCollaboration.objects.get_or_create(
                post_owner=me,
                post_id=int(pid),
                collaborator=cu,
                defaults={"status": PostCollaboration.Status.PENDING},
            )
            if created:
                Notification.objects.create(
                    user=cu,
                    kind=Notification.Kind.COLLAB_INVITE,
                    payload={
                        "post_owner_id": me.id,
                        "post_owner_username": me.username,
                        "post_id": int(pid),
                        "collab_id": pc.pk,
                    },
                )
    return {"ok": True, "post_id": int(pid)}


class PostIdIn(Schema):
    post_id: int


class PostUpdateIn(Schema):
    post_id: int
    title: str
    body: str
    hashtag: Optional[str] = None
    mood: Optional[str] = None
    visibility: int = 0
    is_draft: bool = False


@router.post("/update", auth=auth, response={200: dict, 400: dict})
def update_post_api(request, payload: PostUpdateIn):
    me: User = request.auth
    pid = int(payload.post_id or 0)
    if pid <= 0:
        return 400, {"ok": False, "detail": "post_id required"}
    title = (payload.title or "").strip()[:50]
    body = (payload.body or "").strip()[:255]
    hashtag = (payload.hashtag or "").strip()
    if hashtag and not hashtag.startswith("#"):
        hashtag = f"#{hashtag}"
    mood = (payload.mood or "").strip()
    if mood and not Kayfiyat.objects.filter(slug=mood, is_active=True).exists():
        mood = ""
    if not mood:
        mood = (
            Kayfiyat.objects.filter(is_primary=True, is_active=True)
            .order_by("sort_order", "name")
            .values_list("slug", flat=True)
            .first()
            or "quvnoq"
        )
    vis = max(0, min(3, int(payload.visibility or 0)))
    blog_storage.update_post(
        user_id=me.id,
        username=me.username,
        post_id=pid,
        title=title,
        body=body,
        mood=mood,
        hashtag=hashtag or None,
        visibility=vis,
        is_draft=bool(payload.is_draft),
    )
    return {"ok": True}


@router.post("/delete", auth=auth, response={200: dict, 400: dict})
def delete_post_api(request, payload: PostIdIn):
    me: User = request.auth
    pid = int(payload.post_id or 0)
    if pid <= 0:
        return 400, {"ok": False, "detail": "post_id required"}
    blog_storage.delete_post(user_id=me.id, username=me.username, post_id=pid)
    return {"ok": True}


@router.post("/toggle-public", auth=auth, response={200: dict, 400: dict})
def toggle_public_api(request, payload: PostIdIn):
    me: User = request.auth
    pid = int(payload.post_id or 0)
    if pid <= 0:
        return 400, {"ok": False, "detail": "post_id required"}
    blog_storage.toggle_post_public(user_id=me.id, username=me.username, post_id=pid)
    return {"ok": True}

