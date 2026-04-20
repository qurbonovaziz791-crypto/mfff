# MYFEEL (mf3) — loyiha tahlili (v1.0.0)

Bu hujjat **1-bosqich (v1)** relizidagi loyihani qamrab oladi: arxitektura, URL’lar, UI/UX, asosiy modullar (shu jumladan **Hayriyalar**), saqlash va xavfsizlik eslatmalari. Yangi ish boshlash yoki refaktor uchun yagona qo‘llanma sifatida yangilanadi.

---

## 1. Texnologik stack

| Qatlam | Tanlov |
|--------|--------|
| Backend | **Django 6.x**, funksional view’lar |
| Asosiy DB | **SQLite** (`db.sqlite3`) — foydalanuvchilar, bildirishnomalar, izohlar, yaqinlik, hammualliflik, **hayriya holatlari va shikoyatlar** |
| Postlar (xotiralar) | **Har foydalanuvchi uchun alohida SQLite** (`user_dbs/db.<user_id>.sqlite3`) — `blogs/storage.py` |
| Frontend | Django templates, **HTMX**, Alpine.js, Tailwind fallback CSS, Bootstrap Icons (qisman), **`hybrid-shell.css`** |
| Xarita (hayriyalar) | **Google Maps JavaScript API** — `GOOGLE_MAPS_API_KEY` muhit o‘zgaruvchisi (`config/settings.py`) |
| API | **Django Ninja** (`/api/`, bot router) |
| Statik | `static/css/hybrid-shell.css` — shell, hayriya reels, plastik karta, forma va hokazo |

---

## 2. Arxitektura

### 2.1. Ikki qavatli saqlash

1. Markaziy SQLite — ijtimoiy graf, bildirishnomalar, **CharityCase**, **CharityComplaint** va boshqalar.
2. Postlar — per-user SQLite (`blog_storage` orqali).
3. **`blogs.models.Post`** — migratsiya/legacy bilan bog‘liq bo‘lishi mumkin; asosiy oqim **`blogs.storage`** bilan ishlaydi.

### 2.2. Ilova tuzilmasi

| Ilova | Vazifasi |
|-------|----------|
| **`users`** | Autentifikatsiya, profil, lenta, faoliyat, post detail, compose/archive/stats, recap, hashtag explore, API, SW |
| **`blogs`** | `Kayfiyat`, formlar, `storage` (SQLite CRUD, kalendar, statistika, global hashtag) |
| **`charities`** | Hayriya holatlari: ro‘yxat, batafsil, superuser forma (qo‘shish/tahrirlash), shikoyat, filtrlash |

### 2.3. URL xaritasi (asosiy)

**Loyiha ildizi** (`config/urls.py`): `admin/`, `api/`, **`hayriyalar/`** (`charities.urls`), qolgani `users.urls`.

| Yo‘l | Nomi | Ma’nosi |
|------|------|---------|
| `/` | `login` | Kirish |
| `/auth/<uuid>/` | `magic_link_auth` | Magic link |
| `/feed/` | `home_feed` | «Siz uchun» lenta |
| `/feed/mark-seen/` | `mark_feed_seen` | Postni «ko‘rdim» |
| `/feed/hx/interaction/` | `feed_hx_interaction` | HTMX (masalan, repost) |
| `/activity/` | `activity` | Bildirishnomalar / faoliyat |
| `/hayriyalar/` | `charity_list` | Hayriyalar ro‘yxati (filtr, reels) |
| `/hayriyalar/qoshish/` | `charity_create` | Yangi hayriya (superuser) |
| `/hayriyalar/<slug>/` | `charity_detail` | Batafsil |
| `/hayriyalar/<slug>/tahrirlash/` | `charity_edit` | Tahrir (superuser) |
| `/hayriyalar/<slug>/shikoyat/` | `charity_complaint` | Shikoyat (POST) |
| `/profile/...` | (ko‘p) | Profil, compose, arxiv, stats, post, hashtag, recap… |
| `/api/` | Ninja API | Bot va integratsiya |

---

## 3. Dizayn tizimi (UI/UX)

### 3.1. Hybrid shell

- **Ranglar / shrift**: oq fon, iOS uslubidagi aksent (`#007AFF`), **Inter**.
- **Desktop (≥1024px)**: chap **sidebar** (`hy-sidebar`), markazda kontent, pastki navigatsiya yo‘q.
- **Mobil (<1024px)**:
  - **Yuqori topbar** (`hy-topbar`): logo (lenta), **Hayriyalar**, **His qilish**, **bildirishnoma** (kirgan foydalanuvchi); mehmon uchun **Hayriyalar** + **Kirish**.
  - **Pastki navigatsiya** (`hy-bottom-nav`):
    - **Mehmon**: butun bar **yashirin** — barcha asosiy havolalar yuqorida.
    - **Kirgan**: **His qilish / Hayriyalar / Faoliyat** pastda **ko‘rinmaydi** (yuqorida bor); qoladi: **Siz uchun**, **Missiyalar**, **Xabarlar**, **Profil** (placeholder va profil uchun).
- Komponentlar: post kartalari, hayriya **reels**, filtrlash `<details>`, plastik **to‘lov kartasi**, Google xarita, forma kartalari, faoliyat, arxiv, statistika va hokazo — asosan `hybrid-shell.css`.

### 3.2. Asosiy shablonlar

- `base.html` — CSS tartibi, HTMX, `hybrid_navigation`, `hybrid_header`, `hy-content`.
- `includes/hybrid_navigation.html` — sidebar + mobil pastki menyu (yuqoridagi qoida bilan).
- `includes/hybrid_header.html` — mobil topbar.
- `includes/hybrid_icon.html`, `hybrid_account_panel.html`, `post_card.html` va boshqalar.

### 3.3. Profil va boshqa sahifalar

- Profil: hybrid + `profile.css` aralashmasi; egasi o‘z **bio/viloyat/havolalar** blokini ko‘rmaydi (boshqalar ko‘radi).
- **Hayriyalar** shablonlari: `templates/charities/list.html`, `detail.html`, `case_form.html`, `includes/plastic_card_marks.html`.

### 3.4. Til

- `LANGUAGE_CODE` bo‘yicha interfeys asosan **o‘zbek (lotin)**.

---

## 4. Funksional modullar

### 4.1. Autentifikatsiya va foydalanuvchi

- Login, magic link, `User` (telegram, telefon, foto, bio, viloyat, havolalar JSON, tekshiruv maydonlari).

### 4.2. Lenta, profil, his qilish, post, faoliyat, arxiv, statistika, hashtag, recap

- Avvalgi tahlil bilan bir xil mantiq: `blog_storage`, ko‘rinish qoidalari, repost (HTMX), hammualliflik, izohlar, kayfiyatlar (admin), global hashtag, recap/eksport.

### 4.3. Hayriyalar (`charities`) — v1

**Maqsad:** tekshirilgan yordam holatlarini jamiyatga ko‘rsatish; kiritish — **superuser** (forma orqali).

**Model `CharityCase` (asosiy maydonlar):**

- Kontent: sarlavha, slug, teaser, body, video, poster.
- Holat: `status` (qoralama, tekshiruvda, nashr, yopilgan), `category` (tibbiy, ta’lim, uy-joy, favqulodda, oilaviy, oziq-ovqat, boshqa).
- Joylashuv: viloyat (`users.Region`), tuman, manzil, **latitude/longitude** (ixtiyoriy).
- Aloqa: telefon, **payment_info** (matn, ogohlantirish bilan).
- Yig‘im: **goal_amount**, **collected_amount** (so‘m, ixtiyoriy), progress foizi (`collection_percent`).
- Boshqa: `is_publicly_verified`, `sort_order`, `verified_note`, `created_by`, vaqt belgilari.

**Shikoyat:** autentifikatsiya qilingan foydalanuvchi nashr etilgan holat uchun **CharityComplaint** yuboradi (matn, status).

**Ro‘yxat (`charity_list_view`):**

- Filtr: viloyat, kategoriya, tartib (yangi/eski), «yopilganlarni yashirish».
- Superuser uchun **qoralamalar** `<details>` ichida.
- Kartochkalar: video/poster, progress chizig‘i, **yig‘ilgan / maqsad** — `charity_extras` orqali qisqa format (**ming / mln / mlrd**).

**Batafsil (`charity_detail_view`):**

- Video/poster, maqola, yig‘im bloki (qisqa + to‘liq raqam satri), aloqa (manzil, **Google xarita** — kalit bo‘lsa), telefon nusxa, **to‘lov**:
  - Plastik karta UI: PAN formatlash, **BIN** bo‘yicha brend (Visa, Mastercard, UZCARD, HUMO, MIR, UnionPay, umumiy), gradient fonlar va burchak belgilari (`plastic_card_marks.html` + `charities-detail.js`).
- Tegishli kategoriya bo‘yicha boshqa holatlar.
- Shikoyat formasi (kirgan + saytda ochiq holat).

**Forma (create/edit):**

- Barcha asosiy maydonlar; xarita — **Google Maps** (marker, geolokatsiya, reverse geocode manzilga); kalit yo‘q bo‘lsa matn ogohlantirish va qo‘lda koordinata.
- Statik: `charities-form-map.js`.

**Shablon filtrlari (`charities/templatetags/charity_extras.py`):**

- `uzs_compact` — masalan `125 ming so‘m`, `1,5 mln so‘m`.
- `uzs_spaced` — `1 250 000` (tooltip / aniq ko‘rinish).

**Admin:** `CharityCase`, shikoyatlar ro‘yxati (loyihadagi `charities/admin.py` bo‘yicha).

---

## 5. `blogs/storage.py` — qisqa

- Per-user SQLite: post CRUD, kalendar, statistika, hashtag, global ommaviy statistika, recap, eksport.
- Sana solishtirish `created_at` substring orqali — ISO formatga bog‘liq.

---

## 6. Muhit va xavfsizlik

- **`GOOGLE_MAPS_API_KEY`**: muhitda; Google Cloud’da Maps JavaScript API (+ Geocoding tavsiya etiladi).
- **`SECRET_KEY`**, **`DEBUG`**: production uchun alohida sozlash.
- **`payment_info`**: ochiq saytda to‘liq karta raqami xavfli — forma `help_text` ogohlantiradi; plastik UI foydalanuvchi tajribasi uchun.
- Global hashtag/statistika faqat **ommaviy** postlar.
- Per-user SQLite uchun **backup** strategiyasi.

---

## 7. Hali placeholder yoki «keyin»

- **Missiyalar**, **Xabarlar** — ko‘pincha `href="#"` yoki «tez orada».
- Profil menyusida **Draftlar**, **Sevimlilar** — alohida sahifa emas.
- Like UI yo‘q; repost, share, izoh mavjud.
- **Profil** mobil pastki menyuda qolgan (topbarda to‘g‘ridan-to‘g‘ri havola yo‘q — hisob menyusi orqali tahrir/sozlamalar bor).

---

## 8. O‘zgarishlar jurnali (qisqa)

| Sana / reliz | Izoh |
|--------------|------|
| **v1.0.0** | Hayriyalar moduli (reels, filtr, Google xarita, plastik karta + BIN, `uzs_compact`), mobil pastki menyu optimallashtirildi (takrorlar yashirildi / mehmon uchun bar yopiq), `tahlil.md` v1 bo‘yicha yangilandi. |

---

*Keyingi yangilanishlarda yangi URL, model yoki UI qoidasi qo‘shilsa, shu jadval va tegishli bo‘limlarni yangilash tavsiya etiladi.*
