# UI/UX Dizayn Tahlili (Login, Profile va barcha template'lar)

## Umumiy Holat
- Loyiha uslubi iliq gradient (qizil-to'q sariq) brand palitrasi bilan bir xil ruhda.
- `base.html` ichida app shell, desktop sidebar va mobile bottom-nav aniq ajratilgan.
- Profil, tahrirlash va sozlamalar oqimi endi bir-biriga yaqin UX pattern bilan ishlaydi.
- Katta muammo: dizayn inline style ko'p bo'lgani uchun maintainability pasaygan.

## Sahifalar bo'yicha baho

### `templates/users/login.html`
- Kuchli tomoni: split-layout (branding + forma) va kirish oqimi yaxshi ajratilgan.
- Yaxshilanish nuqtasi: CSS juda katta va inline; keyinchalik `static/css/login.css`ga to'liq ko'chirish kerak.
- A11y: input focus holati yaxshi, lekin keyboard-only navigatsiyada icon tugmalar uchun `aria-label` ni oshirish mumkin.

### `templates/base.html`
- Kuchli tomoni: responsive navigatsiya (desktop sidebar + mobile bottom nav) izchil.
- Yaxshilanish nuqtasi: bir nechta linklar `href="#"` holatda turibdi; real route bilan to'ldirish kerak.
- UX: active state hozir statik; `request.path` orqali dinamik qilish foydali.

### `templates/users/profile.html`
- Kuchli tomoni: mobile-first joylashuv sezilarli yaxshilangan.
- Region faqat egasiga ko'rinishi maxfiylik nuqtasida to'g'ri.
- Linklar "Yana/Yopish" bilan progressive reveal bo'lib, profilni toza saqlaydi.
- Yaxshilanish: keyingi bosqichda post grid real kontentga ulanganida skeleton/empty-state standartlashtirish kerak.

### `templates/users/edit_profile.html`
- Kuchli tomoni: forma bloklari yaxshi guruhlangan, mobilga mos grid fallback bor.
- UX: topbar + card pattern ishlaydi, save/cancel harakati aniq.
- Yaxshilanish: validation xatolari uchun field-level error textlarni bir xil formatda berish kerak.

### `templates/users/settings.html`
- Kuchli tomoni: maxfiylik bo'limi alohida va e'tiborli alert bilan ochilgan.
- UX: username/password o'zgartirish oqimi minimal va tushunarli.
- Yaxshilanish: xavfli action (`logout`) boshqa tugmadan semantik ajratilgan, lekin keyinroq "danger zone" section qilish mumkin.

## Dizayn Tizimi bo'yicha tavsiya
- Inline CSS ni bosqichma-bosqich `static/css/*.css`ga ajratish.
- Rangi, radius, shadow, spacing tokenlarini yagona `:root` faylida boshqarish.
- `component-level` class naming (masalan, `profile-*`, `settings-*`) davom ettirish.
- Utility classlar uchun alohida local fallback fayl saqlash (offline barqarorlik uchun).

## Offline Holatga O'tkazish (bajarildi)
- CDN linklari lokal static linklarga almashtirildi.
- Offline vendor fayllar qo'shildi:
  - `static/vendor/tailwind/tailwind-fallback.css`
  - `static/vendor/bootstrap/css/bootstrap.min.css` (minimal subset)
  - `static/vendor/bootstrap-icons/css/bootstrap-icons.min.css` (fallback icon map)
  - `static/vendor/bootstrap/js/bootstrap.bundle.min.js` (placeholder)
  - `static/vendor/htmx/htmx.min.js` (placeholder)

## Eslatma
- Hozirgi offline vendorlar lightweight fallback sifatida ishlaydi.
- Agar kelajakda Bootstrap JS komponentlari (`modal`, `dropdown`, `collapse`) yoki to'liq HTMX kerak bo'lsa, full build fayllarni local static vendor sifatida qo'shish tavsiya etiladi.
