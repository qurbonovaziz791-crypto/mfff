from __future__ import annotations

from difflib import SequenceMatcher

from django.contrib.auth import get_user_model
from django.db.models import Q
from ninja import Router, Schema

from api.auth import MobileOrSessionAuth
from users.models import YaqinRequest

User = get_user_model()

router = Router(tags=["mobile", "search"])
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


class SearchUserOut(Schema):
    id: int
    username: str
    display_name: str = ""
    photo_url: str = ""
    region: str = ""
    state: str = "none"  # accepted|pending_out|pending_in|none
    allow_requests: bool = True


class SearchOut(Schema):
    mode: str
    q: str = ""
    users: list[SearchUserOut]


@router.get("/", auth=auth, response=SearchOut)
def user_search(request, q: str = ""):
    me: User = request.auth
    q = (q or "").strip()
    if q.startswith("@"):
        q = q[1:].strip()

    base = User.objects.filter(is_active=True).exclude(pk=me.pk)
    mode = "suggested" if not q else "search"

    users: list[User] = []
    if q:
        q_short = q[:2]
        pool = list(
            base.filter(
                Q(username__icontains=q_short) | Q(first_name__icontains=q) | Q(last_name__icontains=q)
            )
            .only("id", "username", "first_name", "last_name", "photo", "region", "allow_yaqin_requests")
            .order_by("username")[:220]
        )
        scored = [(u, _score(u, q)) for u in pool]
        scored.sort(key=lambda t: (t[1], t[0].username), reverse=True)
        users = [u for (u, sc) in scored if sc > 0.15][:30]
    else:
        viewer_region = getattr(me, "region", None)
        cand_qs = base
        if viewer_region:
            cand_qs = cand_qs.filter(region=viewer_region)
        users = list(
            cand_qs.only("id", "username", "first_name", "last_name", "photo", "region", "allow_yaqin_requests")
            .order_by("username")[:20]
        )
        if len(users) < 20:
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
    accepted = set()
    pending_out = set()
    pending_in = set()
    if ids:
        rels = list(
            YaqinRequest.objects.filter(
                Q(from_user=me, to_user_id__in=ids) | Q(to_user=me, from_user_id__in=ids)
            ).only("from_user_id", "to_user_id", "status")
        )
        for r in rels:
            if r.status == YaqinRequest.Status.ACCEPTED:
                other = r.to_user_id if r.from_user_id == me.pk else r.from_user_id
                accepted.add(int(other))
            elif r.status == YaqinRequest.Status.PENDING:
                if r.from_user_id == me.pk:
                    pending_out.add(int(r.to_user_id))
                elif r.to_user_id == me.pk:
                    pending_in.add(int(r.from_user_id))

    out: list[SearchUserOut] = []
    for u in users:
        uid = int(u.pk)
        if uid in accepted:
            st = "accepted"
        elif uid in pending_out:
            st = "pending_out"
        elif uid in pending_in:
            st = "pending_in"
        else:
            st = "none"
        out.append(
            SearchUserOut(
                id=uid,
                username=str(u.username),
                display_name=_display_name(u),
                photo_url=_abs_media_url(request, _photo_url(u)),
                region=str(getattr(u, "region", "") or ""),
                state=st,
                allow_requests=bool(getattr(u, "allow_yaqin_requests", True)),
            )
        )
    return SearchOut(mode=mode, q=q, users=out)

