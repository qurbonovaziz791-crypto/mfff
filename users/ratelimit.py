from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from django.core.cache import cache
from django.http import HttpRequest, HttpResponse


def _client_ip(request: HttpRequest) -> str:
    # Reverse-proxy bo'lsa X-Forwarded-For ni ham ko'rib chiqish mumkin,
    # lekin hozir default REMOTE_ADDR yetarli.
    return (request.META.get("REMOTE_ADDR") or "0.0.0.0").strip()


@dataclass(frozen=True)
class RateLimit:
    key_prefix: str
    limit: int
    window_seconds: int
    key_func: Optional[Callable[[HttpRequest], str]] = None

    def key(self, request: HttpRequest) -> str:
        suffix = self.key_func(request) if self.key_func else _client_ip(request)
        return f"rl:{self.key_prefix}:{suffix}"


def ratelimit(rl: RateLimit) -> Callable:
    def deco(view_func: Callable) -> Callable:
        def wrapped(request: HttpRequest, *args, **kwargs):
            k = rl.key(request)
            try:
                cur = cache.get(k)
                if cur is None:
                    cache.add(k, 1, timeout=rl.window_seconds)
                    cur = 1
                else:
                    cur = cache.incr(k)
            except Exception:
                # Cache ishlamasa ham view ishlasin.
                return view_func(request, *args, **kwargs)

            if int(cur) > int(rl.limit):
                return HttpResponse("Too Many Requests", status=429)
            return view_func(request, *args, **kwargs)

        return wrapped

    return deco

