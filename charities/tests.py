from __future__ import annotations

import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from charities.models import CharityCase, CharityStatus, CharityCategory


User = get_user_model()


class CharityViewsTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.admin = User.objects.create_superuser(
            username="admin",
            password="adminpass123",
            telegram_id="admin-tg",
        )
        # User.save() username'ni auto my-feel-<id> qilib yuboradi, shuning uchun real username'ni olamiz.
        self.admin.refresh_from_db()

    def test_charity_list_ok(self):
        resp = self.client.get(reverse("charity_list"))
        self.assertEqual(resp.status_code, 200)

    def test_charity_detail_404_for_draft_anon(self):
        c = CharityCase.objects.create(
            title="T1",
            teaser="t",
            body="b",
            status=CharityStatus.DRAFT,
            category=CharityCategory.OTHER,
            region="tashkent_city",
            district="d",
            address="a",
            contact_phone="1",
        )
        resp = self.client.get(reverse("charity_detail", kwargs={"slug": c.slug}))
        self.assertEqual(resp.status_code, 404)

    def test_charity_detail_ok_for_published_anon(self):
        c = CharityCase.objects.create(
            title="T2",
            teaser="t",
            body="b",
            status=CharityStatus.PUBLISHED,
            category=CharityCategory.OTHER,
            region="tashkent_city",
            district="d",
            address="a",
            contact_phone="1",
        )
        resp = self.client.get(reverse("charity_detail", kwargs={"slug": c.slug}))
        self.assertEqual(resp.status_code, 200)

    def test_charity_create_requires_login(self):
        resp = self.client.get(reverse("charity_create"))
        self.assertIn(resp.status_code, (301, 302))

    def test_charity_create_superuser_can_open(self):
        self.client.login(username=self.admin.username, password="adminpass123")
        resp = self.client.get(reverse("charity_create"))
        self.assertEqual(resp.status_code, 200)

    def test_charity_create_with_poster_upload(self):
        self.client.login(username=self.admin.username, password="adminpass123")
        with tempfile.TemporaryDirectory() as td:
            media_root = Path(td)
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL="/media/"):
                poster = SimpleUploadedFile(
                    "poster.jpg",
                    b"\xff\xd8\xff\xe0" + b"0" * 2048,
                    content_type="image/jpeg",
                )
                resp = self.client.post(
                    reverse("charity_create"),
                    data={
                        "title": "Xayriya",
                        "teaser": "t",
                        "body": "b",
                        "status": CharityStatus.PUBLISHED,
                        "category": CharityCategory.OTHER,
                        "region": "tashkent_city",
                        "district": "d",
                        "address": "a",
                        "contact_phone": "1",
                        "poster": poster,
                    },
                )
                # create view redirects to detail
                self.assertIn(resp.status_code, (301, 302))
                obj = CharityCase.objects.order_by("-id").first()
                self.assertTrue(obj is not None)
                self.assertTrue(bool(obj.poster))
                self.assertTrue((media_root / obj.poster.name).exists())

