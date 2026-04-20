from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


@dataclass
class EnvFile:
    path: Path

    def read_lines(self) -> list[str]:
        if not self.path.exists():
            return []
        return self.path.read_text(encoding="utf-8").splitlines()

    def set(self, key: str, value: str) -> None:
        lines = self.read_lines()
        out: list[str] = []
        found = False
        prefix = f"{key}="
        for line in lines:
            if line.startswith(prefix):
                out.append(f"{key}={value}")
                found = True
            else:
                out.append(line)
        if not found:
            if out and out[-1].strip() != "":
                out.append("")
            out.append(f"{key}={value}")
        self.path.write_text("\n".join(out) + "\n", encoding="utf-8")


def _normalize_host(host: str) -> str:
    h = (host or "").strip()
    if h.startswith("http://"):
        h = h.removeprefix("http://")
    if h.startswith("https://"):
        h = h.removeprefix("https://")
    h = h.rstrip("/")
    return h


class Command(BaseCommand):
    help = "Update .env host/origin settings for deploy (ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, SITE_URL, API_BASE_URL)."

    def add_arguments(self, parser):
        parser.add_argument("host", help="Server host/ip (e.g. 12.34.56.78 or my-feel.uz)")
        parser.add_argument("--port", default="", help="Optional port (e.g. 8001).")
        parser.add_argument("--scheme", default="", help="http or https (default: https if port empty else http).")
        parser.add_argument(
            "--print-only",
            action="store_true",
            help="Do not write .env, only print suggested values.",
        )

    def handle(self, *args, **opts):
        host = _normalize_host(str(opts.get("host") or ""))
        port = str(opts.get("port") or "").strip()
        scheme = str(opts.get("scheme") or "").strip().lower()
        if not host:
            raise SystemExit("host required")
        if scheme not in {"", "http", "https"}:
            raise SystemExit("--scheme must be http or https")
        if not scheme:
            scheme = "http" if port else "https"

        base = f"{scheme}://{host}" + (f":{port}" if port else "")

        # ALLOWED_HOSTS accepts host[:port] only in some contexts; keep it as host.
        allowed = ",".join(
            sorted(
                {
                    host,
                    "127.0.0.1",
                    "localhost",
                }
            )
        )
        csrf = ",".join(sorted({base, f"{scheme}://{host}"}))

        base_dir = Path(getattr(settings, "BASE_DIR", Path.cwd()))
        env_path = base_dir / ".env"
        self.stdout.write(f".env path: {env_path}")

        # Always print values (copy/paste friendly).
        self.stdout.write(f"- DJANGO_ALLOWED_HOSTS={allowed}")
        self.stdout.write(f"- DJANGO_CSRF_TRUSTED_ORIGINS={csrf}")
        self.stdout.write(f"- SITE_URL={base}")
        self.stdout.write(f"- API_BASE_URL={base}")

        if bool(opts.get("print_only")):
            return

        env = EnvFile(env_path)
        env.set("DJANGO_ALLOWED_HOSTS", allowed)
        env.set("DJANGO_CSRF_TRUSTED_ORIGINS", csrf)
        env.set("SITE_URL", base)
        env.set("API_BASE_URL", base)

        self.stdout.write(self.style.SUCCESS("Updated .env successfully. Restart server/bot to reload env."))

