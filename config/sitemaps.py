from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from charities.models import CharityCase, CharityStatus


class CharityCaseSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.7

    def items(self):
        return CharityCase.objects.filter(
            status__in=(CharityStatus.PUBLISHED, CharityStatus.CLOSED),
        ).order_by("-updated_at")

    def lastmod(self, obj: CharityCase):
        return obj.updated_at


class StaticViewSitemap(Sitemap):
    priority = 0.4
    changefreq = "weekly"

    def items(self):
        return ["charity_list", "home_feed", "activity"]

    def location(self, item):
        return reverse(item)

