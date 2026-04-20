import multiprocessing
import os


bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8001")
chdir = os.environ.get("GUNICORN_CHDIR", ".")

# SQLite bilan eng barqaror yo'l: kam worker.
# (Ko'paytirish = lock ehtimoli oshadi.)
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
threads = int(os.environ.get("GUNICORN_THREADS", "2"))

timeout = int(os.environ.get("GUNICORN_TIMEOUT", "60"))
graceful_timeout = int(os.environ.get("GUNICORN_GRACEFUL_TIMEOUT", "30"))
keepalive = int(os.environ.get("GUNICORN_KEEPALIVE", "5"))

accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

preload_app = os.environ.get("GUNICORN_PRELOAD_APP", "0").strip() in {"1", "true", "yes", "on"}
