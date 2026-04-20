from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse


User = get_user_model()


class SitemapRobotsAndCatchAllTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create_user(
            username="my-feel-test2",
            password="pass12345",
            telegram_id="t2",
        )

    def test_robots_txt_ok(self):
        resp = self.client.get("/robots.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Sitemap:", resp.content.decode("utf-8"))

    def test_sitemap_xml_ok(self):
        # home_feed requires login in sitemap items, but sitemap endpoint itself should render
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<urlset", resp.content.decode("utf-8"))

    def test_catch_all_redirects_to_home(self):
        resp = self.client.get("/some/unknown/path", follow=False)
        self.assertIn(resp.status_code, (301, 302))
        self.assertEqual(resp.headers.get("Location"), "/")

    def test_sw_js_ok(self):
        resp = self.client.get("/sw.js")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("service worker", resp.content.decode("utf-8").lower())
