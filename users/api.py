import secrets
from typing import Optional

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from ninja import Router, Schema

User = get_user_model()
router = Router(tags=["bot"])


def _rl_key(request, *, prefix: str) -> str:
    ip = ""
    try:
        ip = request.META.get("REMOTE_ADDR", "")
    except Exception:
        ip = ""
    return f"rl:{prefix}:{ip or '0.0.0.0'}"


def _rate_limit(request, *, prefix: str, limit: int, window_s: int) -> Optional[dict]:
    k = _rl_key(request, prefix=prefix)
    try:
        cur = cache.get(k)
        if cur is None:
            cache.add(k, 1, timeout=window_s)
            cur = 1
        else:
            cur = cache.incr(k)
    except Exception:
        return None
    if int(cur) > int(limit):
        return {"status": "error", "message": "Too Many Requests", "code": 429}
    return None


def _require_bearer(request) -> Optional[dict]:
    """
    Productionda /api/bot/* endpointlar faqat Bearer token bilan.
    DEBUG'da token bo'sh bo'lsa lokal dev uchun ruxsat beramiz.
    """
    token = getattr(settings, "API_BEARER_TOKEN", "") or ""
    if settings.DEBUG and not token:
        return None
    auth = ""
    try:
        auth = request.headers.get("Authorization", "")
    except Exception:
        auth = request.META.get("HTTP_AUTHORIZATION", "")
    if not auth.startswith("Bearer "):
        return {"status": "error", "message": "Unauthorized", "code": 401}
    provided = auth.removeprefix("Bearer ").strip()
    if not provided or not token or not secrets.compare_digest(provided, token):
        return {"status": "error", "message": "Unauthorized", "code": 401}
    return None


def _abs_login_link(lk_uuid: str) -> str:
    base = (getattr(settings, "SITE_URL", "") or "").rstrip("/")
    if not base:
        # fallback: request host bo'lmasa ham ishlasin (dev)
        return f"/auth/{lk_uuid}/"
    return f"{base}/auth/{lk_uuid}/"


class RegisterInput(Schema):
    telegram_id: str
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None

class ChangeCredentialsInput(Schema):
    telegram_id: str
    new_username: Optional[str] = None
    new_password: Optional[str] = None

@router.post("/register/")
def register_bot_user(request, data: RegisterInput):
    rl = _rate_limit(request, prefix="api_bot_register", limit=60, window_s=60)
    if rl:
        return rl
    err = _require_bearer(request)
    if err:
        return err
    user, created = User.objects.get_or_create(
        telegram_id=data.telegram_id,
        defaults={
            'phone': data.phone,
            'first_name': data.first_name or "",
            'last_name': data.last_name or ""
        }
    )
    
    # MVP: eski logika saqlandi (DBga tegmaymiz), lekin prod'da buni keyinroq mustahkamlash kerak.
    raw_password = data.telegram_id[::-1]
    
    if created:
        user.set_password(raw_password)
        user.save()
        # lk_uuid is auto-generated in the save method of the first creation
    else:
        # User avvaldan bo'lsa ham, phone bo'sh bo'lsa yangilab qo'yamiz
        updated = False
        if data.phone and not user.phone:
            user.phone = data.phone
            updated = True
        # (ixtiyoriy) ism/familiyani ham bo'sh bo'lsa to'ldiramiz
        if (data.first_name and not user.first_name):
            user.first_name = data.first_name
            updated = True
        if (data.last_name and not user.last_name):
            user.last_name = data.last_name
            updated = True
        if updated:
            user.save(update_fields=["phone", "first_name", "last_name"])
    
    return {
        "status": "success",
        "message": "User registered" if created else "User already exists",
        "login": user.username,
        "password": raw_password if created else "hidden",
        "login_link": _abs_login_link(user.lk_uuid),
    }

@router.post("/change-credentials/")
def change_credentials(request, data: ChangeCredentialsInput):
    rl = _rate_limit(request, prefix="api_bot_change", limit=60, window_s=60)
    if rl:
        return rl
    err = _require_bearer(request)
    if err:
        return err
    try:
        user = User.objects.get(telegram_id=data.telegram_id)
    except User.DoesNotExist:
        return {"status": "error", "message": "User not found"}
        
    old_password = data.telegram_id[::-1]
    
    if data.new_username:
        user.username = data.new_username
    if data.new_password:
        user.set_password(data.new_password)
        
    user.save()
    
    return {
        "status": "success",
        "login": user.username,
        "password": data.new_password or old_password,
        "login_link": _abs_login_link(user.lk_uuid),
    }
