from __future__ import annotations

import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from django.contrib.auth import get_user_model

User = get_user_model()


class WebSmokeTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    def test_login_page_ok(self):
        resp = self.client.get(reverse("login"))
        self.assertEqual(resp.status_code, 200)

    def test_feed_requires_login(self):
        resp = self.client.get(reverse("home_feed"))
        # login_required -> redirect to login
        self.assertIn(resp.status_code, (301, 302))

    def test_magic_link_auth_redirects(self):
        u = User.objects.create_user(
            # username my-feel- bilan boshlangan bo'lsa, save() lk_uuid'ni set qilmaydi.
            username="magic",
            password="pass12345",
            telegram_id="tg-magic",
        )
        resp = self.client.get(f"/auth/{u.lk_uuid}/", follow=False)
        self.assertIn(resp.status_code, (301, 302))
        self.assertEqual(resp.headers.get("Location"), reverse("home_feed"))


class BotApiAuthTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()

    @override_settings(DEBUG=False, API_BEARER_TOKEN="test-token", SITE_URL="https://example.com")
    def test_bot_register_requires_bearer(self):
        resp = self.client.post(
            "/api/bot/register/",
            data={
                "telegram_id": "123",
                "phone": "+998900000000",
                "first_name": "A",
                "last_name": "B",
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("code"), 401)

    @override_settings(DEBUG=False, API_BEARER_TOKEN="test-token", SITE_URL="https://example.com")
    def test_bot_register_ok_with_bearer(self):
        resp = self.client.post(
            "/api/bot/register/",
            data={
                "telegram_id": "123",
                "phone": "+998900000000",
                "first_name": "A",
                "last_name": "B",
            },
            content_type="application/json",
            **{"HTTP_AUTHORIZATION": "Bearer test-token"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data.get("status"), "success")
        self.assertIn("login_link", data)
        self.assertTrue(str(data["login_link"]).startswith("https://example.com/"))


class MediaUploadTests(TestCase):
    def setUp(self) -> None:
        self.client = Client()
        self.user = User.objects.create_user(
            # User.save() birinchi creationda username'ni auto "my-feel-<id>" qilib yuboradi.
            # Shuning uchun login testlarda aniq ishlashi uchun shu prefix bilan yaratamiz.
            username="my-feel-test",
            password="pass12345",
            telegram_id="t1",
        )
        self.client.login(username=self.user.username, password="pass12345")

    def test_profile_photo_upload_saves_file(self):
        with tempfile.TemporaryDirectory() as td:
            media_root = Path(td)
            with override_settings(MEDIA_ROOT=media_root, MEDIA_URL="/media/"):
                upload = SimpleUploadedFile(
                    "avatar.jpg",
                    b"\xff\xd8\xff\xe0" + b"0" * 1024,
                    content_type="image/jpeg",
                )
                resp = self.client.post(
                    reverse("profile_edit"),
                    data={
                        "first_name": "A",
                        "last_name": "B",
                        "bio": "bio",
                        "gender": "",
                        "dob": "",
                        "region": "",
                        "photo": upload,
                    },
                )
                self.assertIn(resp.status_code, (301, 302))
                self.user.refresh_from_db()
                self.assertTrue(bool(self.user.photo))
                # storage file should exist on disk
                self.assertTrue((media_root / self.user.photo.name).exists())
