from __future__ import annotations

from typing import Optional

from django.contrib.auth import get_user_model
from django.db.models import Q
from ninja import Router, Schema

from api.auth import MobileOrSessionAuth
from charities.models import (
    CharityCase,
    CharityCategory,
    CharityComplaint,
    CharityStatus,
    CharityUpdate,
)
from users.models import Region

User = get_user_model()

router = Router(tags=["mobile", "charities"])
auth = MobileOrSessionAuth()


def _abs_url(request, maybe_path: str) -> str:
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


class CharityCaseOut(Schema):
    id: int
    title: str
    slug: str
    teaser: str
    status: str
    category: str
    region: str
    district: str
    address: str = ""
    poster_url: str = ""
    video_url: str = ""
    is_publicly_verified: bool = False
    goal_amount: Optional[str] = None
    collected_amount: Optional[str] = None
    collection_percent: Optional[int] = None
    created_at: str
    updated_at: str


class CharityListOut(Schema):
    cases: list[CharityCaseOut]
    page: int
    page_size: int
    has_next: bool
    region_choices: list[tuple[str, str]]
    category_choices: list[tuple[str, str]]


@router.get("/", auth=auth, response=CharityListOut)
def charity_list(
    request,
    q: str = "",
    region: str = "",
    category: str = "",
    sort: str = "new",
    hide_closed: bool = False,
    page: int = 1,
    page_size: int = 20,
):
    qs = CharityCase.objects.filter(status__in=(CharityStatus.PUBLISHED, CharityStatus.CLOSED))
    q = (q or "").strip()
    region = (region or "").strip()
    category = (category or "").strip()
    sort = (sort or "new").strip()

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(teaser__icontains=q)
            | Q(body__icontains=q)
            | Q(district__icontains=q)
            | Q(address__icontains=q)
        )
    if region:
        qs = qs.filter(region=region)
    if category:
        qs = qs.filter(category=category)
    if hide_closed:
        qs = qs.exclude(status=CharityStatus.CLOSED)

    if sort == "old":
        qs = qs.order_by("sort_order", "created_at")
    else:
        qs = qs.order_by("sort_order", "-created_at")

    p = max(1, int(page or 1))
    ps = max(1, min(50, int(page_size or 20)))
    start = (p - 1) * ps
    end = start + ps
    rows = list(qs.select_related("created_by")[start:end])
    has_next = qs.count() > end

    out: list[CharityCaseOut] = []
    for c in rows:
        out.append(
            CharityCaseOut(
                id=int(c.id),
                title=str(c.title),
                slug=str(c.slug),
                teaser=str(c.teaser),
                status=str(c.status),
                category=str(c.category),
                region=str(c.region),
                district=str(c.district),
                address=str(c.address or "")[:180],
                poster_url=_abs_url(request, c.poster.url) if getattr(c, "poster", None) else "",
                video_url=_abs_url(request, c.video.url) if getattr(c, "video", None) else "",
                is_publicly_verified=bool(getattr(c, "is_publicly_verified", False)),
                goal_amount=str(c.goal_amount) if c.goal_amount is not None else None,
                collected_amount=str(c.collected_amount) if c.collected_amount is not None else None,
                collection_percent=c.collection_percent,
                created_at=c.created_at.isoformat(),
                updated_at=c.updated_at.isoformat(),
            )
        )

    return CharityListOut(
        cases=out,
        page=p,
        page_size=ps,
        has_next=bool(has_next),
        region_choices=[(k, v) for (k, v) in Region.choices],
        category_choices=[(k, v) for (k, v) in CharityCategory.choices],
    )


class CharityUpdateOut(Schema):
    id: int
    message: str
    created_at: str


class CharityDetailOut(Schema):
    case: CharityCaseOut
    body: str
    address: str
    contact_phone: str
    payment_info: str = ""
    payment_click_url: str = ""
    payment_payme_url: str = ""
    payment_other_label: str = ""
    payment_other_url: str = ""
    goal_amount: Optional[str] = None
    collected_amount: Optional[str] = None
    collection_percent: Optional[int] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    updates: list[CharityUpdateOut]
    related: list[CharityCaseOut]


@router.get("/{slug}", auth=auth, response={200: CharityDetailOut, 404: dict})
def charity_detail(request, slug: str):
    c = CharityCase.objects.filter(slug=slug).first()
    if not c:
        return 404, {"ok": False, "detail": "Not found"}
    if not c.is_public_on_site:
        # allow superuser via session/token
        u: User = request.auth
        if not getattr(u, "is_superuser", False):
            return 404, {"ok": False, "detail": "Not found"}

    updates = list(c.updates.all().order_by("-created_at")[:20])
    related = (
        CharityCase.objects.filter(status__in=(CharityStatus.PUBLISHED, CharityStatus.CLOSED))
        .filter(region=c.region)
        .exclude(pk=c.pk)
        .order_by("sort_order", "-created_at")[:5]
    )
    case_out = CharityCaseOut(
        id=int(c.id),
        title=str(c.title),
        slug=str(c.slug),
        teaser=str(c.teaser),
        status=str(c.status),
        category=str(c.category),
        region=str(c.region),
        district=str(c.district),
        address=str(c.address or "")[:180],
        poster_url=_abs_url(request, c.poster.url) if c.poster else "",
        video_url=_abs_url(request, c.video.url) if c.video else "",
        is_publicly_verified=bool(getattr(c, "is_publicly_verified", False)),
        goal_amount=str(c.goal_amount) if c.goal_amount is not None else None,
        collected_amount=str(c.collected_amount) if c.collected_amount is not None else None,
        collection_percent=c.collection_percent,
        created_at=c.created_at.isoformat(),
        updated_at=c.updated_at.isoformat(),
    )
    return CharityDetailOut(
        case=case_out,
        body=str(c.body or ""),
        address=str(c.address or ""),
        contact_phone=str(c.contact_phone or ""),
        payment_info=str(c.payment_info or ""),
        payment_click_url=str(c.payment_click_url or ""),
        payment_payme_url=str(c.payment_payme_url or ""),
        payment_other_label=str(c.payment_other_label or ""),
        payment_other_url=str(c.payment_other_url or ""),
        goal_amount=str(c.goal_amount) if c.goal_amount is not None else None,
        collected_amount=str(c.collected_amount) if c.collected_amount is not None else None,
        collection_percent=c.collection_percent,
        latitude=float(c.latitude) if c.latitude is not None else None,
        longitude=float(c.longitude) if c.longitude is not None else None,
        updates=[CharityUpdateOut(id=int(u.id), message=str(u.message), created_at=u.created_at.isoformat()) for u in updates],
        related=[
            CharityCaseOut(
                id=int(r.id),
                title=str(r.title),
                slug=str(r.slug),
                teaser=str(r.teaser),
                status=str(r.status),
                category=str(r.category),
                region=str(r.region),
                district=str(r.district),
                poster_url=_abs_url(request, r.poster.url) if r.poster else "",
                video_url=_abs_url(request, r.video.url) if r.video else "",
                is_publicly_verified=bool(getattr(r, "is_publicly_verified", False)),
                created_at=r.created_at.isoformat(),
                updated_at=r.updated_at.isoformat(),
            )
            for r in related
        ],
    )


class ComplaintIn(Schema):
    message: str


@router.post("/{slug}/complaint", auth=auth, response={200: dict, 400: dict, 404: dict})
def charity_complaint(request, slug: str, payload: ComplaintIn):
    u: User = request.auth
    c = CharityCase.objects.filter(slug=slug, status__in=(CharityStatus.PUBLISHED, CharityStatus.CLOSED)).first()
    if not c:
        return 404, {"ok": False, "detail": "Not found"}
    msg = (payload.message or "").strip()
    if len(msg) < 8:
        return 400, {"ok": False, "detail": "Message too short"}
    if len(msg) > 2000:
        msg = msg[:2000]
    CharityComplaint.objects.create(charity_case=c, reporter=u, message=msg)
    return {"ok": True}

