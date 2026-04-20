from __future__ import annotations

from typing import Optional

from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.contrib.auth import get_user_model
from ninja.security import HttpBearer

User = get_user_model()


class MobileTokenAuth:
    """
    Shared mobile Bearer token logic.
    Implemented here to avoid circular imports between `api.auth` and routers.
    """

    def __init__(self, *, max_age_seconds: int = 60 * 60 * 24 * 30):
        self.signer = TimestampSigner(salt="myfeel.mobile.v1")
        self.max_age_seconds = int(max_age_seconds)

    def authenticate(self, request, token: str) -> Optional[User]:
        if not token:
            return None
        try:
            raw = self.signer.unsign(token, max_age=self.max_age_seconds)
            uid = int(raw)
        except (BadSignature, SignatureExpired, ValueError):
            return None
        return User.objects.filter(id=uid, is_active=True).first()

    def issue(self, user: User) -> str:
        return self.signer.sign(str(int(user.id)))


mobile_token_auth = MobileTokenAuth()


class MobileOrSessionAuth(HttpBearer):
    """
    Accept either:
    - Authorization: Bearer <token>  (mobile token)
    - Django session (request.user authenticated) for web pages / CSRF-protected forms

    NOTE: CSRF is enforced by Django middleware for session-authenticated unsafe methods.
    """

    def authenticate(self, request, token: str) -> Optional[User]:
        # 1) Bearer token (preferred for mobile)
        if token:
            try:
                u = mobile_token_auth.authenticate(request, token)
                if u:
                    return u
            except Exception:
                pass

        # 2) Session auth (web)
        try:
            u = getattr(request, "user", None)
            if u is not None and getattr(u, "is_authenticated", False) and getattr(u, "is_active", False):
                return u
        except Exception:
            return None
        return None

