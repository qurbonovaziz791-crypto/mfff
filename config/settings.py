import os
import sys
from urllib.parse import urlparse
from django.db.backends.signals import connection_created
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Optional .env loader (dependency'siz) ---
# `.env` mavjud bo'lsa, os.environ'da yo'q qiymatlarni yuklaydi.
def _load_dotenv(path: Path) -> None:
    try:
        if not path.exists():
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        # .env xatosi serverni yiqitmasin
        return


_load_dotenv(BASE_DIR / ".env")

# --- Helpers ---
def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name, "")
    if v == "":
        return default
    return v.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


# Google Maps JavaScript API (Hayriyalar: manzil xaritasi). Masalan: export GOOGLE_MAPS_API_KEY="..."
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()

# Telegram bot
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
API_BEARER_TOKEN = os.environ.get("API_BEARER_TOKEN", "").strip()


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "").strip() or "dev-only-unsafe"

DEBUG = _env_bool("DJANGO_DEBUG", default=False)

ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS") or (["*"] if DEBUG else [])


INSTALLED_APPS = [
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'users.apps.UsersConfig',
    'blogs.apps.BlogsConfig',
    'charities.apps.CharitiesConfig',
]

MIDDLEWARE = [
    "django.middleware.gzip.GZipMiddleware",
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        # Prod'da template render tezligi uchun cached loader ishlatamiz.
        # DEBUG=True bo'lganda autoreload qulayligi uchun APP_DIRS=True qoldiramiz.
        'APP_DIRS': DEBUG,
        'OPTIONS': {
            **(
                {}
                if DEBUG
                else {
                    "loaders": [
                        (
                            "django.template.loaders.cached.Loader",
                            [
                                "django.template.loaders.filesystem.Loader",
                                "django.template.loaders.app_directories.Loader",
                            ],
                        )
                    ]
                }
            ),
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'users.context_processors.activity_badge',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'



DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        # SQLite: MVP uchun tez va kam "qotish" (single-instance tavsiya)
        "OPTIONS": {
            # Django sqlite backend uses `uri=True` only if NAME starts with "file:"
            # so pragmalarni connection_created signal bilan beramiz (pastda).
            "timeout": int(os.environ.get("SQLITE_TIMEOUT", "30")),
        },
    }
}

# SQLite pragmalar (request paytida lock kamroq bo‘lishi uchun).
# Eslatma: bu arxitektura baribir single-instance (1 app server) uchun.
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    SQLITE_PRAGMAS = [
        ("journal_mode", os.environ.get("SQLITE_JOURNAL_MODE", "WAL")),
        ("synchronous", os.environ.get("SQLITE_SYNCHRONOUS", "NORMAL")),
        ("temp_store", "MEMORY"),
        ("foreign_keys", "ON"),
        ("cache_size", os.environ.get("SQLITE_CACHE_SIZE", "-20000")),  # ~20MB
        ("busy_timeout", os.environ.get("SQLITE_BUSY_TIMEOUT", "5000")),
    ]


def _apply_sqlite_pragmas(sender, connection, **kwargs):
    if connection.vendor != "sqlite":
        return
    pragmas = globals().get("SQLITE_PRAGMAS", [])
    if not pragmas:
        return
    with connection.cursor() as cursor:
        for k, v in pragmas:
            cursor.execute(f"PRAGMA {k}={v};")


connection_created.connect(_apply_sqlite_pragmas)


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'uz-uz'

TIME_ZONE = 'Asia/Tashkent'

USE_I18N = True

USE_TZ = True


# --- Cache (Redis recommended for 1k–10k users) ---
REDIS_URL = (os.environ.get("REDIS_URL", "") or "").strip()
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "20"))

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "TIMEOUT": CACHE_TTL_SECONDS,
        }
    }
else:
    # Dev fallback
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "mf3-local",
            "TIMEOUT": CACHE_TTL_SECONDS,
        }
    }


# --- Celery (background jobs) ---
CELERY_BROKER_URL = (os.environ.get("CELERY_BROKER_URL", "") or REDIS_URL or "").strip()
CELERY_RESULT_BACKEND = (os.environ.get("CELERY_RESULT_BACKEND", "") or CELERY_BROKER_URL or "").strip()
CELERY_TASK_ALWAYS_EAGER = _env_bool("CELERY_TASK_ALWAYS_EAGER", default=DEBUG)
CELERY_TASK_EAGER_PROPAGATES = True


STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# WhiteNoise: cache static aggressively in prod.
# Manifest storage already versions hashed files; this max_age mainly affects non-versioned files.
WHITENOISE_MAX_AGE = int(os.environ.get("WHITENOISE_MAX_AGE", "31536000" if not DEBUG else "0"))

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

AUTH_USER_MODEL = 'users.User'

LOGIN_URL = "/"
LOGIN_REDIRECT_URL = "/feed/"

# --- CORS/CSRF (prod’da aniq originlar bilan) ---
# corsheaders qat'iy bool kutadi (ba'zi muhitlarda env qiymati noto'g'ri parse bo'lishi mumkin),
# shuning uchun plain bool'ga majburan keltiramiz.
CORS_ALLOW_ALL_ORIGINS = True if _env_bool("DJANGO_CORS_ALLOW_ALL_ORIGINS", default=DEBUG) else False
CORS_ALLOWED_ORIGINS = _env_list("DJANGO_CORS_ALLOWED_ORIGINS")

CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS")

# --- Production security defaults (HTTPS + reverse proxy) ---
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = _env_bool("DJANGO_SECURE_SSL_REDIRECT", default=not DEBUG)
SESSION_COOKIE_SECURE = _env_bool("DJANGO_SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = _env_bool("DJANGO_CSRF_COOKIE_SECURE", default=not DEBUG)
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "0" if DEBUG else "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=not DEBUG)
SECURE_HSTS_PRELOAD = _env_bool("DJANGO_SECURE_HSTS_PRELOAD", default=not DEBUG)
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Cookie samesite (login flow uchun Lax yetarli)
SESSION_COOKIE_SAMESITE = os.environ.get("DJANGO_SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = os.environ.get("DJANGO_CSRF_COOKIE_SAMESITE", "Lax")

# Allowed hosts bo‘sh qolib ketmasin (prod’da majburiy)
_missing_prod_env = (SECRET_KEY == "dev-only-unsafe" or not ALLOWED_HOSTS)
_dev_mgmt_cmds = {
    "runserver",
    "collectstatic",
    "migrate",
    "makemigrations",
    "createsuperuser",
    "shell",
    "check",
    "deploy_check",
}
_is_dev_mgmt = any(arg in _dev_mgmt_cmds for arg in sys.argv)
if not DEBUG and _missing_prod_env:
    # Lokal dev'da boshqaruv komandalarini (runserver/collectstatic/migrate/...) ishlashi uchun yumshatamiz.
    # Prod/gunicorn'da esa env majburiy bo'lib qoladi.
    if _is_dev_mgmt:
        DEBUG = True
        ALLOWED_HOSTS = ["*"]
    else:
        raise RuntimeError("Production uchun env sozlanmagan: DJANGO_SECRET_KEY va DJANGO_ALLOWED_HOSTS kerak.")

# --- Base URL (bot linklari, absolute URLlar) ---
SITE_URL = os.environ.get("SITE_URL", "").strip().rstrip("/")
if not SITE_URL and not DEBUG and ALLOWED_HOSTS:
    # birinchi hostdan taxmin qilamiz (nginx HTTPS bo‘ladi)
    SITE_URL = f"https://{ALLOWED_HOSTS[0]}"

# --- Logging (gunicorn/systemd bilan yaxshi ishlaydi) ---
LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "INFO" if not DEBUG else "DEBUG").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "%(levelname)s %(name)s %(message)s"},
        "verbose": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        # runserver'da HTTPS (TLS) paketlar kelib qolsa 400 spam bo'ladi — jim qilamiz.
        # Asosiy app loglari baribir root orqali chiqadi.
        "django.server": {"handlers": ["console"], "level": "CRITICAL", "propagate": False},
    },
}

# Upload limitlar (DM upload 15MB, charity video bo‘lishi mumkin)
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE", str(25 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE", str(5 * 1024 * 1024)))

# --- Bot API protection ---
API_BEARER_TOKEN = os.environ.get("API_BEARER_TOKEN", "").strip()

# DEBUG=False bo'lsa ham media serve qilish (Nginx yo'q/test uchun).
SERVE_MEDIA = _env_bool("DJANGO_SERVE_MEDIA", default=False)

