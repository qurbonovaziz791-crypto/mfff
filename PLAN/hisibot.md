# MYFEEL (`mf3`) — StartApp darajasida baholash (hisob-kitob)

Sana: 2026-04-02  
Repo: `c:\Users\Egamov_O\Desktop\mf3`

## 1) Qisqa xulosa

Ushbu repoda **Django asosidagi MVP** bor: veb (login/profile/postlar) + **Telegram bot** (aiogram) + **Django Ninja API** orqali botdan user yaratish/credentials almashtirish.

Startap darajasida “ishga tushirish” uchun eng katta gap — **production tayyorgarligi**: konfiguratsiya (env), dependency boshqaruvi (`requirements.txt`), deploy (gunicorn/uvicorn + nginx), DB (PostgreSQL), xavfsizlik (tokenlar, API auth), monitoring/logging va minimal testlar.

Quyida 2 xil baho berildi:
- **A — Mavjud MVPni productionga chiqarish** (hozirgi funksiyalar doirasida).
- **B — `PLAN/implementation_plan.md` dagi to‘liq StartApp roadmap** (map/chat/realtime/celery/redis/flutter va h.k.).

## 2) Hozirgi funksional holat (kod bo‘yicha)

### 2.1 Backend (Django)
- **Custom `User` modeli**: `users/models.py`
  - `telegram_id` unique, `lk_uuid` (magic-link), profil maydonlari (photo, gender, dob, region, bio, links JSON).
- **Auth oqimi**: `users/views.py`
  - Login (username/password), logout.
  - Magic-link: `/auth/<lk_uuid>/` → avtomatik login.
  - Settings: username/password almashtirish (session hash update).
- **Postlar**: `blogs/models.py`, `blogs/forms.py`, `users/views.py`
  - Create/delete, public/private toggle, qidiruv (title/body/hashtag), sana bo‘yicha filter, pagination.
- **API (Bot uchun)**: `config/urls.py`, `users/api.py`
  - `POST /api/bot/register/`
  - `POST /api/bot/change-credentials/`

### 2.2 Frontend (Django templates)
- UI shell: `templates/base.html` (responsive sidebar + mobile bottom-nav).
- Sahifalar: `templates/users/login.html`, `profile.html`, `edit_profile.html`, `settings.html`.
- Statiklar: `static/` (vendor bootstrap/icons/htmx va css).

### 2.3 Telegram bot
- `bot.py` (aiogram + aiohttp):
  - `/start` — API orqali ro‘yxatdan o‘tish va login link berish.
  - `/change_login`, `/change_password` — API orqali credentials yangilash.

## 3) StartApp darajasida kritik risklar (tezkor tekshiruv)

### 3.1 Xavfsizlik (kritik)
- **`SECRET_KEY` kodda va `DEBUG=True`, `ALLOWED_HOSTS=["*"]`** (`config/settings.py`).
- **Telegram `BOT_TOKEN` kodda ochiq** (`bot.py`).
- **Bot API endpointlari hozircha autentifikatsiyasiz** (`users/api.py`). Istalgan odam `POST /api/bot/register/` chaqirishi mumkin.

> Bu bandlar productionga chiqishdan oldin **majburiy** yopiladi: `.env`/secret manager, `DEBUG=False`, hostlar, HTTPS, API token (Bearer) + rate-limit.

### 3.2 Deploy/infra (repo ichida yo‘q)
- `requirements.txt` / `pyproject.toml` ko‘rinmayapti (dependency reproduksiya qiyin).
- Dockerfile / docker-compose / Procfile yo‘q (deploy standartlashmagan).
- SQLite default (`db.sqlite3`) — production uchun odatda PostgreSQL kerak bo‘ladi.

## 4) Baholash modeli (StartApp darajasida)

### Ish uslubi
- 1 MVP backend engineer (Django) + 1 frontend (template/UI) + kerak bo‘lsa DevOps (part-time).
- QA minimal (smoke + asosiy user flow).

### Stavka diapazoni (bozor bo‘yicha)
- **$15–$30 / soat** (freelance/mini-team, lokal bozor).
- Alternativ: fixed-price paket.

> Valyuta: USD ko‘rsatildi. UZSga o‘tkazish kursi bozorga qarab o‘zgaradi.

## 5) Narx va muddat (2 ssenariy)

### A) Mavjud MVP (web + bot) ni productionga chiqarish
**Scope**: mavjud funksiyalarni saqlagan holda production tayyorlash.

**Ishlar ro‘yxati (high-level)**:
- Konfiguratsiya: `.env` + settings split (dev/prod), secretlarni ko‘chirish.
- Dependency: `requirements.txt` (yoki `pyproject.toml`) + README.
- DB: PostgreSQL migratsiya (xohishga ko‘ra), media/static yig‘ish.
- Bot API himoyasi: `Authorization: Bearer <TOKEN>` (yoki HMAC), rate-limit, minimal audit logging.
- Deploy: gunicorn/uvicorn + nginx + systemd/Docker, HTTPS (Let’s Encrypt), monitoring (basic).
- Xatoliklar: 404/500, logging, admin hardening.
- Minimal testlar: auth + post create/toggle/delete, API register/change.

**Taxminiy ish hajmi**:
- Backend (Django + API + security): **40–80 soat**
- Frontend (template polish + edge-cases): **16–40 soat**
- Bot (prod config, retry, timeouts, secrets): **8–20 soat**
- DevOps/Deploy: **16–40 soat**
- QA/bugfix buffer: **16–32 soat**

**Jami**: **96–212 soat**

**Narx (stavka $15–$30/soat)**:
- **$1,440 – $6,360**

**Muddat**:
- 1 kishilik rejim: **2–5 hafta**
- 2 kishilik kichik jamoa: **1–3 hafta**

### B) `PLAN/implementation_plan.md` dagi to‘liq StartApp roadmap (katta MVP)
Bu hujjatda ko‘rsatilgan yo‘nalishlar (masalan: Flutter app, realtime chat/channels, redis/celery, map/postgis, scaling) hozirgi repoda **to‘liq implement qilinmagan**; bu allaqachon “MVP+” yoki “v1” darajadagi katta ish.

**Qo‘shimcha modullar (rejadagi)**:
- Mobile/Web frontend: **Flutter** (alohida repo/katta modul)
- Realtime: Django Channels, websocket chat/matchmaking
- Celery + Redis (background jobs, scheduled tasks)
- PostgreSQL + PostGIS (map/geo)
- Push notification, analytics, moderation, anti-abuse
- CI/CD, staging, observability

**Taxminiy ish hajmi** (minimal to‘liq ishlaydigan v1 uchun):
- Backend platforma + realtime + jobs + DB: **240–480 soat**
- Flutter app (MVP screens + auth + feed/chat): **280–600 soat**
- DevOps (prod+staging+CI/CD+monitoring): **60–140 soat**
- QA + bugfix buffer: **80–160 soat**

**Jami**: **660–1,380 soat**

**Narx (stavka $15–$30/soat)**:
- **$9,900 – $41,400**

**Muddat**:
- 2–3 kishilik jamoa: **2–4 oy**
- 4–6 kishilik jamoa: **1.5–3 oy**

## 6) “Tez yutish” tavsiyalari (narxni tushirish uchun)
- **A ssenariy bilan chiqish**: hozirgi web+bot MVP’ni productionga chiqarib validatsiya qilish.
- Flutter/realtime’ni keyingi iteratsiyaga qoldirish (traffic/monetizatsiya signalidan keyin).
- Map/chat kabi og‘ir modullarni “placeholder” yoki minimal prototip bilan boshlash.

## 7) Minimal “Production checklist” (A ssenariy uchun)
- [ ] Secretlar `.env` ga: `SECRET_KEY`, `BOT_TOKEN`, `API_BEARER_TOKEN`, DB creds
- [ ] `DEBUG=False`, `ALLOWED_HOSTS` aniq
- [ ] Bot API: Bearer auth + rate limit + log
- [ ] `requirements.txt`/README + “how to run”
- [ ] PostgreSQL (ixtiyoriy, lekin tavsiya)
- [ ] Deploy: nginx + app server, HTTPS, static/media
- [ ] Backup (DB + media) va basic monitoring

---

## 8) Yakuniy baho (1 qatorda)
- **Mavjud MVPni StartApp darajasida productionga chiqarish**: **$1.4k – $6.4k** (taxminan 2–5 hafta).  
- **Rejadagi to‘liq platforma (Flutter + realtime + infra)**: **$9.9k – $41.4k** (taxminan 2–4 oy).

