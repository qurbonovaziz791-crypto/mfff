$ErrorActionPreference = "Stop"

python .\manage.py migrate --noinput
python .\manage.py collectstatic --noinput

# Windows'da gunicorn fcntl talab qiladi (Unix only). Shu sabab waitress ishlatamiz.
$bind = $env:WAITRESS_LISTEN
if ([string]::IsNullOrWhiteSpace($bind)) { $bind = "127.0.0.1:8001" }

python -m waitress --listen=$bind config.wsgi:application
