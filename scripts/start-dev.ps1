$ErrorActionPreference = "Stop"

# Dev uchun: production cheklovlarini o'chirib, HTTP runserver ko'taramiz.
# Eslatma: bu faqat lokal test uchun.

$env:DJANGO_DEBUG = "1"
$env:DJANGO_ALLOWED_HOSTS = "*"
$env:DJANGO_SECRET_KEY = "dev-only"

# HTTPS/prod security redirectlarini o'chiramiz (runserver HTTPS bilmaydi)
$env:DJANGO_SECURE_SSL_REDIRECT = "0"
$env:DJANGO_SESSION_COOKIE_SECURE = "0"
$env:DJANGO_CSRF_COOKIE_SECURE = "0"
$env:DJANGO_SECURE_HSTS_SECONDS = "0"
$env:DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS = "0"
$env:DJANGO_SECURE_HSTS_PRELOAD = "0"

# Lokal originlar (xohlasangiz)
$env:DJANGO_CORS_ALLOW_ALL_ORIGINS = "1"

python .\manage.py runserver 127.0.0.1:8000

