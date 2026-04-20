from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.utils import timezone
from ninja import Router, Schema
from api.auth import MobileOrSessionAuth, mobile_token_auth

User = get_user_model()


auth = MobileOrSessionAuth()
router = Router(tags=["mobile", "users"])


class LoginIn(Schema):
    username: str
    password: str


class TokenOut(Schema):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int


class UserProfileOut(Schema):
    id: int
    username: str
    first_name: str = ""
    last_name: str = ""
    is_verified: bool = False
    photo_url: str = ""
    bio: str = ""
    region: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[str] = None


class LoginOut(Schema):
    token: TokenOut
    me: UserProfileOut


class BaseOut(Schema):
    me: UserProfileOut
    server_time: str
    media_base_url: str


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


def _user_out(request, u: User) -> UserProfileOut:
    return UserProfileOut(
        id=int(u.id),
        username=str(u.username),
        first_name=str(getattr(u, "first_name", "") or ""),
        last_name=str(getattr(u, "last_name", "") or ""),
        is_verified=bool(getattr(u, "is_verified", False)),
        photo_url=_abs_media_url(request, _photo_url(u)),
        bio=str(getattr(u, "bio", "") or ""),
        region=getattr(u, "region", None) or None,
        gender=getattr(u, "gender", None) or None,
        dob=str(getattr(u, "dob", "") or "") or None,
    )


def _issue_token(user: User) -> TokenOut:
    tok = mobile_token_auth.issue(user)
    return TokenOut(access_token=tok, expires_in=int(mobile_token_auth.max_age_seconds))


@router.post("/login", response={200: LoginOut, 401: dict})
def mobile_login(request, payload: LoginIn):
    username = (payload.username or "").strip()
    password = payload.password or ""
    user = authenticate(request, username=username, password=password)
    if not user or not getattr(user, "is_active", False):
        return 401, {"ok": False, "detail": "Invalid credentials"}
    return LoginOut(token=_issue_token(user), me=_user_out(request, user))


@router.get("/me", auth=auth, response=UserProfileOut)
def mobile_me(request):
    return _user_out(request, request.auth)


@router.get("/base", auth=auth, response=BaseOut)
def mobile_base(request):
    return BaseOut(
        me=_user_out(request, request.auth),
        server_time=timezone.now().isoformat(),
        media_base_url=str(getattr(settings, "MEDIA_URL", "/media/")),
    )


@router.get("/profile/{username}", auth=auth, response={200: UserProfileOut, 404: dict})
def mobile_profile(request, username: str):
    u = User.objects.filter(username=username, is_active=True).first()
    if not u:
        return 404, {"ok": False, "detail": "Not found"}
    return _user_out(request, u)


class MeUpdateIn(Schema):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None
    region: Optional[str] = None
    gender: Optional[str] = None
    dob: Optional[str] = None


@router.post("/me/update", auth=auth, response=UserProfileOut)
def mobile_me_update(request, payload: MeUpdateIn):
    """
    Fast profile editing for mobile/web.
    Photo upload can be added later (multipart); this updates text fields.
    """
    u: User = request.auth
    changed = False

    def _set(attr: str, val: Optional[str]):
        nonlocal changed
        if val is None:
            return
        try:
            setattr(u, attr, val)
            changed = True
        except Exception:
            return

    _set("first_name", (payload.first_name or "").strip())
    _set("last_name", (payload.last_name or "").strip())
    _set("bio", (payload.bio or "").strip())
    _set("region", (payload.region or None))
    _set("gender", (payload.gender or None))
    _set("dob", (payload.dob or None))

    if changed:
        u.save(update_fields=["first_name", "last_name", "bio", "region", "gender", "dob"])
    return _user_out(request, u)

