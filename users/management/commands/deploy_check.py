from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Deployment readiness checks (env/static/media/sqlite/api)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Fail on missing production env even in DEBUG.",
        )

    def _ok(self, msg: str) -> None:
        self.stdout.write(self.style.SUCCESS(f"OK  {msg}"))

    def _warn(self, msg: str) -> None:
        self.stdout.write(self.style.WARNING(f"WARN {msg}"))

    def _err(self, msg: str) -> None:
        self.stdout.write(self.style.ERROR(f"ERR  {msg}"))

    def handle(self, *args, **opts):
        strict = bool(opts.get("strict"))
        problems = 0

        self.stdout.write("=== mf3 deploy_check ===")
        self.stdout.write(f"DEBUG={settings.DEBUG}")
        self.stdout.write(f"ALLOWED_HOSTS={getattr(settings, 'ALLOWED_HOSTS', None)}")
        self.stdout.write(f"STATIC_ROOT={getattr(settings, 'STATIC_ROOT', None)}")
        self.stdout.write(f"MEDIA_ROOT={getattr(settings, 'MEDIA_ROOT', None)}")
        self.stdout.write("")

        # 1) Required env (prod)
        secret_key = (getattr(settings, "SECRET_KEY", "") or "").strip()
        allowed_hosts = getattr(settings, "ALLOWED_HOSTS", []) or []
        if (not settings.DEBUG or strict) and (not secret_key or secret_key == "dev-only-unsafe"):
            problems += 1
            self._err("DJANGO_SECRET_KEY set emas (prod uchun majburiy).")
        else:
            self._ok("SECRET_KEY bor.")

        if (not settings.DEBUG or strict) and (not allowed_hosts or allowed_hosts == ["*"]):
            problems += 1
            self._err("DJANGO_ALLOWED_HOSTS aniq emas (prod uchun domen qo'ying).")
        else:
            self._ok("ALLOWED_HOSTS ok.")

        # 2) Whitenoise present
        try:
            import whitenoise  # noqa: F401
        except Exception:
            problems += 1
            self._err("whitenoise o'rnatilmagan. `pip install -r requirements.txt` qiling.")
        else:
            self._ok("whitenoise import ok.")

        # 3) Static collected?
        static_root = Path(str(getattr(settings, "STATIC_ROOT", "")))
        if not static_root or str(static_root) in {"", "."}:
            problems += 1
            self._err("STATIC_ROOT noto'g'ri.")
        else:
            if static_root.exists() and any(static_root.rglob("*")):
                self._ok(f"staticfiles bor: {static_root}")
            else:
                self._warn(f"staticfiles topilmadi: {static_root} (collectstatic kerak bo'lishi mumkin)")

        # 4) Media root writable?
        media_root = Path(str(getattr(settings, "MEDIA_ROOT", "")))
        try:
            media_root.mkdir(parents=True, exist_ok=True)
            probe = media_root / ".write_test"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except Exception as e:
            problems += 1
            self._err(f"MEDIA_ROOT yozib bo'lmaydi: {media_root} ({e})")
        else:
            self._ok(f"MEDIA_ROOT writable: {media_root}")

        # 5) SQLite: DB file writable + basic query
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                _ = cursor.fetchone()
        except Exception as e:
            problems += 1
            self._err(f"DB ulanish xato: {e}")
        else:
            self._ok("DB query ok.")

        if connection.vendor == "sqlite":
            db_name = connection.settings_dict.get("NAME")
            p = Path(str(db_name))
            try:
                p.parent.mkdir(parents=True, exist_ok=True)
                # touch-write test
                with open(p, "a", encoding="utf-8"):
                    pass
            except Exception as e:
                problems += 1
                self._err(f"SQLite fayliga yozib bo'lmaydi: {p} ({e})")
            else:
                self._ok(f"SQLite file ok: {p}")

        # 6) Bot API token
        api_token = (getattr(settings, "API_BEARER_TOKEN", "") or "").strip()
        if not api_token and not settings.DEBUG:
            problems += 1
            self._err("API_BEARER_TOKEN set emas (prod uchun majburiy).")
        elif not api_token:
            self._warn("API_BEARER_TOKEN yo'q (DEBUG rejimda ruxsat).")
        else:
            self._ok("API_BEARER_TOKEN bor.")

        # 7) Helpful hints for common browser error
        self.stdout.write("")
        self.stdout.write("=== Browser tip ===")
        self.stdout.write("runserver faqat HTTP. Brauzerda: http://127.0.0.1:8000/ (https emas)")

        self.stdout.write("")
        if problems:
            self._err(f"deploy_check: {problems} ta muammo topildi.")
            raise SystemExit(2)
        self._ok("deploy_check: hammasi joyida (asosiy tekshiruvlar).")

