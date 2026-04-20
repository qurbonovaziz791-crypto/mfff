from __future__ import annotations

from django import template

from blogs.models import Kayfiyat
from blogs.storage import mood_label as _mood_label

register = template.Library()


@register.filter(name="mood_label")
def mood_label_filter(mood: str) -> str:
    return _mood_label(mood)


@register.filter(name="get_item")
def get_item_filter(mapping, key):
    if not mapping:
        return ""
    try:
        if hasattr(mapping, "get"):
            v = mapping.get(key)
            if v is not None:
                return v
            if isinstance(key, str) and key.isdigit():
                return mapping.get(int(key), "")
    except (TypeError, ValueError, KeyError):
        pass
    return ""


@register.filter(name="mood_emoji")
def mood_emoji_filter(mood: str) -> str:
    if not mood:
        return ""
    k = Kayfiyat.objects.filter(slug=str(mood).strip()).first()
    if k and (k.emoji or "").strip():
        return (k.emoji or "").strip()
    label = _mood_label(mood)
    return (label or "")[:2]

