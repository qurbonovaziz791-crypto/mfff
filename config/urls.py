from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView, RedirectView
from ninja import NinjaAPI
from users.api import router as bot_router
from api.users.mobile import router as mobile_users_router
from api.posts.mobile import router as mobile_posts_router
from api.posts.actions import router as mobile_posts_actions_router
from api.posts.detail import router as mobile_posts_detail_router
from api.feed.mobile import router as mobile_feed_router
from api.search.mobile import router as mobile_search_router
from api.activity.mobile import router as mobile_activity_router
from api.yaqin.mobile import router as mobile_yaqin_router
from api.dm.mobile import router as mobile_dm_router
from api.charities.mobile import router as mobile_charities_router
from api.insights.mobile import router as mobile_insights_router
from .sitemaps import CharityCaseSitemap, StaticViewSitemap

api = NinjaAPI(title="MYFEEL API", version="1.0.0")
api.add_router("/bot/", bot_router)
api.add_router("/mobile/users/", mobile_users_router)
api.add_router("/mobile/posts/", mobile_posts_router)
api.add_router("/mobile/posts/", mobile_posts_actions_router)
api.add_router("/mobile/posts/", mobile_posts_detail_router)
api.add_router("/mobile/feed/", mobile_feed_router)
api.add_router("/mobile/search/", mobile_search_router)
api.add_router("/mobile/activity/", mobile_activity_router)
api.add_router("/mobile/yaqin/", mobile_yaqin_router)
api.add_router("/mobile/dm/", mobile_dm_router)
api.add_router("/mobile/charities/", mobile_charities_router)
api.add_router("/mobile/insights/", mobile_insights_router)

SITEMAPS = {
    "static": StaticViewSitemap,
    "charities": CharityCaseSitemap,
}

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', api.urls),
    path("robots.txt", TemplateView.as_view(template_name="robots.txt", content_type="text/plain")),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="django.contrib.sitemaps.views.sitemap"),
    path('hayriyalar/', include('charities.urls')),
    path('', include('users.urls')),
    
]

# Media fayllar:
# - DEBUG=True bo'lsa avtomatik serve qilamiz.
# - DEBUG=False bo'lsa ham, Nginx yo'q/test muhitda `DJANGO_SERVE_MEDIA=1` bilan yoqish mumkin.
if settings.DEBUG or bool(getattr(settings, "SERVE_MEDIA", False)):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Catch-all: nomalum URL → home page ("/")
# Eslatma: bu SEO uchun emas, lekin mobil/SPA uslubidagi navigatsiyada qulay.
urlpatterns += [
    re_path(r"^(?!admin/|api/|static/|media/).*$", RedirectView.as_view(url="/", permanent=False)),
]
