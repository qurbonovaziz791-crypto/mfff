"""Hayriyalar shablonlari: so‘mni qisqa (ming / mln / mlrd) va to‘liq bo‘shliqli ko‘rinish."""

from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

# Shablonlardagi bilan bir xil apostrof (’)
_SOM = "so\u2019m"


def _to_int(value):
    if value is None or value == "":
        return None
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _triplet_space(n: int) -> str:
    s = str(abs(int(n)))
    parts = []
    while s:
        parts.append(s[-3:])
        s = s[:-3]
    return " ".join(reversed(parts))


def _comma_decimal(val: float, max_dp: int = 2) -> str:
    s = f"{val:.{max_dp}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",")


@register.filter
def uzs_spaced(value):
    """Masalan: 12 500 000 — tooltip va aria uchun."""
    n = _to_int(value)
    if n is None:
        return ""
    sign = "-" if n < 0 else ""
    return sign + _triplet_space(n)


@register.filter
def uzs_compact(value):
    """
    Qisqa o‘qilish: 125 ming, 1,5 mln, 2 mlrd so‘m.
    < 1000: to‘liq bo‘shliq bilan.
    """
    n = _to_int(value)
    if n is None:
        return ""
    neg = n < 0
    n = abs(n)
    sign = "-" if neg else ""

    if n < 1000:
        return f"{sign}{_triplet_space(n)} {_SOM}"

    if n < 1_000_000:
        if n % 1000 == 0:
            return f"{sign}{n // 1000} ming {_SOM}"
        v = n / 1000.0
        return f"{sign}{_comma_decimal(v, 2)} ming {_SOM}"

    if n < 1_000_000_000:
        v = n / 1_000_000.0
        if abs(v - round(v)) < 1e-9:
            return f"{sign}{int(round(v))} mln {_SOM}"
        return f"{sign}{_comma_decimal(v, 2)} mln {_SOM}"

    v = n / 1_000_000_000.0
    if abs(v - round(v)) < 1e-9:
        return f"{sign}{int(round(v))} mlrd {_SOM}"
    return f"{sign}{_comma_decimal(v, 2)} mlrd {_SOM}"
