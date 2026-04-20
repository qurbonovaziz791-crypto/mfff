# MYFEEL: Autentifikatsiya va Foydalanuvchi Modeli Rejasi (auth.md)

Ushbu hujjat yangi ijtimoiy tarmog'imizning Autentifikatsiya (Users) tizimini, uning Telegram bot bilan qanday integratsiya qilinishini va profil sahifalarini qanday tashkil etilishini belgilab beradi.

## 1. Loyihaning umumiy ko'rinishi va talablar

*   **Foydalanuvchi Modeli (User):** `users/models.py` da yaratiladi. Avtomatlashtirilgan identifikatorlar va Telegram ma'lumotlariga asoslanadi.
*   **Ro'yxatdan o'tish (Registration):** Faqat Telegram bot orqali ishlaydi. Veb-saytda an'anaviy "Register" sahifasi bo'lmaydi.
*   **Magic Link (lk_uuid):** Har bir foydalanuvchida yagona va maxfiy havola bo'ladi (domen/auth/<lk_uuid>). Bu orqali foydalanuvchi to'g'ridan-to'g'ri tizimga avtorizatsiya qilinadi.
*   **Profil Tizimi:** Instagram dizayniga 1-ga-1 o'xshash bo'lgan `/profile/<username>` manzili orqali qulay profil va tahrirlash (Edit Profile) funksiyalari.

## 2. Taklif etilayotgan O'zgarishlar (Proposed Changes)

### `users` Moduli

#### [NEW] `users/models.py`

Django'ning `AbstractUser` klassini kengaytirgan holda yangi User modelini yozamiz:

```python
import uuid
import hashlib
from django.db import models
from django.contrib.auth.models import AbstractUser

class Region(models.TextChoices):
    TASHKENT_CITY = 'tashkent_city', "Toshkent shahri"
    TASHKENT = 'tashkent', "Toshkent viloyati"
    # ... jami 14 ta hudud kiritiladi
    
class Gender(models.TextChoices):
    MALE = 'male', 'Male'
    FEMALE = 'female', 'Female'

def user_directory_path(instance, filename):
    # Rasm papkasi: media/profile/avatars/<user_id>/filename
    return f'profile/avatars/{instance.id}/{filename}'

class User(AbstractUser):
    telegram_id = models.CharField(max_length=50, unique=True, verbose_name="Telegram ID")
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    # first_name, last_name, username, password AbstractUser-dan keladi
    
    lk_uuid = models.CharField(max_length=255, unique=True, editable=False)
    is_verified = models.BooleanField(default=False, verbose_name="Premium/Galochka")
    photo = models.ImageField(upload_to=user_directory_path, null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, null=True, blank=True)
    dob = models.DateField(null=True, blank=True, verbose_name="Tug'ilgan sana")
    region = models.CharField(max_length=50, choices=Region.choices, null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    links = models.JSONField(default=list, blank=True) # Postgres uchun ArrayField ham ishlatsa bo'ladi
    
    def generate_lk_uuid(self):
        # uuid + login + password kombinatsiyasidan xash yasash
        base_str = f"{uuid.uuid4().hex}:{self.username}:{self.password}"
        return hashlib.sha256(base_str.encode()).hexdigest()

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        # Parol yoki Username o'zgarganda lk_uuid ham o'zgarishi kerak
        if not is_new:
            old_instance = User.objects.get(pk=self.pk)
            if old_instance.username != self.username or old_instance.password != self.password:
                self.lk_uuid = self.generate_lk_uuid()
                
        super().save(*args, **kwargs)
        
        # Yangi foydalanuvchi bo'lsa ID raqamini olganidan keyin Username nomini yaratamiz
        if is_new and not self.username.startswith('my-feel-'):
            self.username = f"my-feel-{self.id}"
            self.lk_uuid = self.generate_lk_uuid()
            self.save(update_fields=['username', 'lk_uuid'])
```

#### [NEW] API Endpoints (Telegram Bot bilan integratsiya uchun)
Telegram botdan so'rov qabul qilib, yozib oluvchi REST API (yoki oddiy Webhook) View'lar yaratiladi:
1.  **`POST /api/bot/register/`**: 
    - Botdan kelgan JSON: `{telegram_id, phone, first_name, last_name}`
    - Backend jarayoni: User yaratadi. Passwordni `telegram_id[::-1]` ga o'rnatadi. Username auto-generatsiya qilinadi. `lk_uuid` yaratiladi.
    - Javob qaytaradi: `login`, `raw_password`, `login_link (domain.uz/auth/<lk_uuid>)`.
2.  **`POST /api/bot/change-credentials/`**:
    - Botda user login yoki parolini o'zgartirganda so'rov keladi.
    - Username va Parol xavfsiz tarzda o'zgartiriladi. `lk_uuid` signal yoki save() orqali avto-yangilanadi.
    - Javob: yangi `login`, `password`, va янги `login_link`.

#### [NEW] Auth Views va Profil Views
1. **Magic Link Login (`/auth/<lk_uuid>/`)**: Shu sahifaga kirganda back-end avtomat tekshirib ushbu userga login (session ochar) qiladi va uni `/profile/<username>` ga yo'naltiradi (redirect).
2. **Profile View (`/profile/<username>/`)**: Instagram kabi UI render qiluvchi sahifa. Faqat egasi ko'rsa "Edit profile" tugmasi chiqadi.
3. **Edit Profile View (`/profile/edit/`)**: `telegram_id` va `phone` dan tashqari barcha fieldlarni o'zgartira oladigan in-page forma.

## 3. UI/UX Dizayn Talablari (Instagram 1-to-1)
*   **Texnologiyalar**: Tailwind CSS, HTML, HTMX (sahifa yangilanmasdan forms yuborish uchun).
*   **Asosiy Sahifa Elementlari**:
    *   **Header**: Username, Galochka iconi, Settings burger menu.
    *   **Profile Stats**: Avatar (chapda), Posts, Followers, Following sonlari (o'ngda).
    *   **Bio Detail**: First Name, Last Name, Bio teksti, va `links` (sayt manzillari - bosiladigan formatda).
    *   **Action Buttons**: Katta "Edit Profile", "Share Profile" tugmalari.
    *   **Tabs**: Posts, Reels, Tagged (hozircha bo'sh tursin yoki placeholder).
*   **Edit Profile Elementlari**: Mobile-first dizayn, rasm upload qilish dumaloq krugda chiqib turadi "Change photo" tugmasi bilan. HTML `input` va `select` (Region uchun) Instagram UI-ga mutlaqo moslangan qora/oq temada (Dark/Light mode).

## 4. Foydalanuvchi Diqqatiga (User Review Required)

> [!IMPORTANT]
> 1. **Havfsizlik:** Bot API larigacha xavfsizlik (ya'ni oddiy odam POST post/bot/register ni chaqirib qo'ymasligi uchun) qanday bo'ladi? Yopiq API Token (Secret Key) bilan tasdiqlanishi kerak. (Masalan, `Authorization: Bearer <SECRET_TOKEN>`). Bunga rozimisiz?
> 2. **Links qismi (Postgres JSON):** Django'da `models.JSONField(default=list)` yoki oddiy xarflardan tashkil topgan `CharField` da vergul bilan ajratib (masalan comma separated values) saqlash ma'qulmi? Biz qulaylik uchun JSONField taklif etdik.
> 3. **lk_uuid format qoidalari:** Siz aytgan "uuid + login + password hash" formati bo'yicha u ancha uzun xesh (256/128 belgi) bo'lib ketadi (masalan, `ab2f9...`). Bu link vizual ravishda uncha chiroyli bo'lmasligi mumkin (`domain.uz/auth/ab2f9d6c.../`). Agar shunga rozilik bersangiz kodda ko'rsatilgan standart SHA-256 hash orqali yozamiz.

---
Agar ushbu reja (Plan) maqbul kelgan bo'lsa, **Tasdiqlashingiz (Approve)** kutiladi! Tasdiqdan so'ng darhol DB modellar va Django Views loyihasini kodlashga (Execute) o'tamiz. jigarim, "Tasdiqlandi, boshla" desangiz bas!
