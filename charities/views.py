from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.db.models import Q
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .forms import CharityCaseForm, CharityComplaintForm
from users.models import Region

from .models import CharityCase, CharityCategory, CharityStatus, CharityUpdate


def _require_superuser(request):
    if not request.user.is_superuser:
        raise PermissionDenied("Faqat superuser hayriyalarni boshqarishi mumkin.")


def _gmaps_ctx():
    return {"google_maps_api_key": getattr(settings, "GOOGLE_MAPS_API_KEY", "") or ""}


def _public_case_queryset():
    return CharityCase.objects.filter(
        status__in=(CharityStatus.PUBLISHED, CharityStatus.CLOSED),
    )


def charity_list_view(request):
    qs = _public_case_queryset()

    q = (request.GET.get("q") or "").strip()
    filter_region = (request.GET.get("region") or "").strip()
    filter_category = (request.GET.get("category") or "").strip()
    sort = (request.GET.get("sort") or "new").strip()
    hide_closed = request.GET.get("hide_closed") == "1"

    if q:
        qs = qs.filter(
            Q(title__icontains=q)
            | Q(teaser__icontains=q)
            | Q(body__icontains=q)
            | Q(district__icontains=q)
            | Q(address__icontains=q)
        )

    if filter_region:
        qs = qs.filter(region=filter_region)
    if filter_category:
        qs = qs.filter(category=filter_category)
    if hide_closed:
        qs = qs.exclude(status=CharityStatus.CLOSED)

    if sort == "old":
        qs = qs.order_by("sort_order", "created_at")
    else:
        qs = qs.order_by("sort_order", "-created_at")

    list_url = request.build_absolute_uri(request.get_full_path())
    ctx = {
        "cases": qs,
        "q": q,
        "filter_region": filter_region,
        "filter_category": filter_category,
        "sort": sort,
        "hide_closed": hide_closed,
        "region_choices": Region.choices,
        "category_choices": CharityCategory.choices,
        "charity_list_share_url": list_url,
    }
    if request.user.is_authenticated and request.user.is_superuser:
        ctx["draft_cases"] = CharityCase.objects.filter(
            status__in=(CharityStatus.DRAFT, CharityStatus.REVIEW),
        ).order_by("sort_order", "-updated_at")
    return render(request, "charities/list.html", ctx)


def charity_detail_view(request, slug):
    case = get_object_or_404(CharityCase, slug=slug)
    if not case.is_public_on_site:
        if not request.user.is_authenticated or not request.user.is_superuser:
            raise Http404()
    related = _related_for_case(case) if case.is_public_on_site else []
    complaint_form = None
    if request.user.is_authenticated and case.is_public_on_site:
        complaint_form = CharityComplaintForm()
    updates = list(case.updates.select_related("created_by").all()[:20])
    share_url = request.build_absolute_uri(case.get_absolute_url())
    og_image = ""
    if case.poster:
        og_image = request.build_absolute_uri(case.poster.url)
    ctx = {
        "case": case,
        "related_cases": related,
        "complaint_form": complaint_form,
        "updates": updates,
        "charity_share_url": share_url,
        "charity_og_image": og_image,
        "charity_og_description": (case.teaser or case.title)[:300],
    }
    ctx.update(_gmaps_ctx())
    return render(request, "charities/detail.html", ctx)


def _related_for_case(case):
    return list(
        _public_case_queryset()
        .filter(region=case.region)
        .exclude(pk=case.pk)
        .order_by("sort_order", "-created_at")[:5]
    )


@login_required
@require_http_methods(["POST"])
def charity_complaint_view(request, slug):
    case = get_object_or_404(CharityCase, slug=slug)
    if not case.is_public_on_site:
        raise Http404()
    form = CharityComplaintForm(request.POST)
    if form.is_valid():
        c = form.save(commit=False)
        c.charity_case = case
        c.reporter = request.user
        c.save()
        messages.success(request, "Shikoyatingiz qabul qilindi. Moderatsiya ko‘rib chiqadi.")
        return redirect(case.get_absolute_url())
    share_url = request.build_absolute_uri(case.get_absolute_url())
    og_image = ""
    if case.poster:
        og_image = request.build_absolute_uri(case.poster.url)
    ctx = {
        "case": case,
        "related_cases": _related_for_case(case),
        "complaint_form": form,
        "updates": list(case.updates.select_related("created_by").all()[:20]),
        "charity_share_url": share_url,
        "charity_og_image": og_image,
        "charity_og_description": (case.teaser or case.title)[:300],
    }
    ctx.update(_gmaps_ctx())
    return render(request, "charities/detail.html", ctx)


@login_required
def charity_create_view(request):
    _require_superuser(request)
    if request.method == "POST":
        form = CharityCaseForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.created_by = request.user
            obj.save()
            messages.success(request, "Hayriya saqlandi.")
            return redirect(obj.get_absolute_url())
    else:
        form = CharityCaseForm()
    ctx = {"form": form, "is_edit": False, "case": None}
    ctx.update(_gmaps_ctx())
    return render(request, "charities/case_form.html", ctx)


@login_required
def charity_edit_view(request, slug):
    _require_superuser(request)
    case = get_object_or_404(CharityCase, slug=slug)
    if request.method == "POST":
        form = CharityCaseForm(request.POST, request.FILES, instance=case)
        if form.is_valid():
            form.save()
            messages.success(request, "O‘zgarishlar saqlandi.")
            return redirect(case.get_absolute_url())
    else:
        form = CharityCaseForm(instance=case)
    ctx = {"form": form, "is_edit": True, "case": case}
    ctx.update(_gmaps_ctx())
    return render(request, "charities/case_form.html", ctx)


@login_required
@require_http_methods(["POST"])
def charity_add_update_view(request, slug):
    _require_superuser(request)
    case = get_object_or_404(CharityCase, slug=slug)
    msg = (request.POST.get("message") or "").strip()
    if len(msg) < 8:
        messages.warning(request, "Yangilanish juda qisqa (kamida 8 belgi).")
        return redirect(case.get_absolute_url() + "#hy-charity-updates")
    if len(msg) > 1200:
        msg = msg[:1200]
    CharityUpdate.objects.create(
        charity_case=case,
        message=msg,
        created_by=request.user,
        created_at=timezone.now(),
    )
    messages.success(request, "Yangilanish qo‘shildi.")
    return redirect(case.get_absolute_url() + "#hy-charity-updates")
