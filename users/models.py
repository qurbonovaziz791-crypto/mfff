import uuid
import hashlib
from django.db import models
from django.contrib.auth.models import AbstractUser

class Region(models.TextChoices):
    TASHKENT_CITY = 'tashkent_city', "Toshkent shahri"
    TASHKENT = 'tashkent', "Toshkent viloyati"
    ANDIJAN = 'andijan', "Andijon viloyati"
    BUKHARA = 'bukhara', "Buxoro viloyati"
    FERGANA = 'fergana', "Farg'ona viloyati"
    JIZZAKH = 'jizzakh', "Jizzax viloyati"
    NAMANGAN = 'namangan', "Namangan viloyati"
    NAVOI = 'navoi', "Navoiy viloyati"
    KASHKADARYA = 'kashkadarya', "Qashqadaryo viloyati"
    SAMARKAND = 'samarkand', "Samarqand viloyati"
    SIRDARYA = 'sirdarya', "Sirdaryo viloyati"
    SURKHANDARYA = 'surkhandarya', "Surxondaryo viloyati"
    KHOREZM = 'khorezm', "Xorazm viloyati"
    KARAKALPAKSTAN = 'karakalpakstan', "Qoraqalpog'iston Respublikasi"

class Gender(models.TextChoices):
    MALE = 'male', 'Male'
    FEMALE = 'female', 'Female'

def user_directory_path(instance, filename):
    return f'profile/avatars/{instance.id}/{filename}'

class User(AbstractUser):
    telegram_id = models.CharField(max_length=50, unique=True, verbose_name="Telegram ID")
    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    
    lk_uuid = models.CharField(max_length=255, unique=True, editable=False)
    is_verified = models.BooleanField(default=False, verbose_name="Premium/Galochka")
    photo = models.ImageField(upload_to=user_directory_path, null=True, blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices, null=True, blank=True)
    dob = models.DateField(null=True, blank=True, verbose_name="Tug'ilgan sana")
    region = models.CharField(max_length=50, choices=Region.choices, null=True, blank=True)
    bio = models.TextField(max_length=500, blank=True)
    links = models.JSONField(default=list, blank=True)

    # Xotira eslatmasi (profilda banner; email uchun cron/management command)
    reminder_enabled = models.BooleanField(default=False, verbose_name="Eslatma yoqilgan")
    reminder_weekday = models.PositiveSmallIntegerField(
        default=6,
        verbose_name="Hafta kuni (0=du, 6=yak)",
        help_text="0=du, 1=se, 2=ch, 3=pa, 4=ju, 5=sha, 6=yak",
    )
    reminder_hour = models.PositiveSmallIntegerField(default=20, verbose_name="Soat (0–23)")

    # Sozlamalar (Instagram-uslubida): compose va maxfiylik
    default_post_visibility = models.PositiveSmallIntegerField(
        default=0,
        verbose_name="Post ko‘rinishi (default)",
        help_text="0=Faqat men, 1=Havola, 2=Yaqinlar, 3=Ochiq",
    )
    compose_autosave_enabled = models.BooleanField(
        default=True,
        verbose_name="Compose autosave",
        help_text="Hissiyot yozishda avtomatik qoralama saqlash (brauzerda).",
    )
    allow_yaqin_requests = models.BooleanField(
        default=True,
        verbose_name="Yaqin so‘rovlari",
        help_text="Boshqalar sizga yaqin bo‘lish so‘rovi yuborishi mumkin.",
    )
    allow_collab_invites = models.BooleanField(
        default=True,
        verbose_name="Hammualliflik takliflari",
        help_text="Boshqalar sizni postiga hammuallif qilib qo‘shishi mumkin.",
    )

    REQUIRED_FIELDS = ['telegram_id']
    
    def generate_lk_uuid(self):
        base_str = f"{uuid.uuid4().hex}:{self.username}:{self.password}"
        return hashlib.sha256(base_str.encode()).hexdigest()

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        
        if not is_new:
            try:
                old_instance = User.objects.get(pk=self.pk)
                if old_instance.username != self.username or old_instance.password != self.password:
                    self.lk_uuid = self.generate_lk_uuid()
            except User.DoesNotExist:
                pass
                
        super().save(*args, **kwargs)
        
        if is_new and not self.username.startswith('my-feel-'):
            self.username = f"my-feel-{self.id}"
            self.lk_uuid = self.generate_lk_uuid()
            self.save(update_fields=['username', 'lk_uuid'])

    def __str__(self):
        return self.username


class Follow(models.Model):
    follower = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="following_rel", db_index=True
    )
    following = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="followers_rel", db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["follower", "following"], name="uniq_follow_pair"),
        ]
        indexes = [
            models.Index(fields=["following", "follower"]),
        ]

    def __str__(self):
        return f"{self.follower_id} → {self.following_id}"


class YaqinRequest(models.Model):
    """Ikki foydalanuvchi o‘rtasida: so‘rov → qabul = «yaqin» (har ikkala tomonda +1)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        ACCEPTED = "accepted", "Qabul qilingan"

    from_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="yaqin_sent", db_index=True
    )
    to_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="yaqin_recv", db_index=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["from_user", "to_user"], name="uniq_yaqin_request_pair"),
        ]
        indexes = [
            models.Index(fields=["to_user", "status"]),
            models.Index(fields=["from_user", "status"]),
        ]

    def __str__(self):
        return f"{self.from_user_id} → {self.to_user_id} ({self.status})"


class Notification(models.Model):
    """In-app bildirishnomalar (yaqinlik so‘rovi, hammualliflik va hokazo)."""

    class Kind(models.TextChoices):
        YAQIN_REQUEST = "yaqin_request", "Yaqinlik so‘rovi"
        COLLAB_INVITE = "collab_invite", "Postga ulashish"
        DM_MESSAGE = "dm_message", "Shaxsiy xabar"
        COMMENT = "comment", "Izoh"
        NEW_POST = "new_post", "Yangi post"

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications", db_index=True
    )
    kind = models.CharField(max_length=32, choices=Kind.choices, db_index=True)
    payload = models.JSONField(default=dict, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["user", "read_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} {self.kind}"


class PostCollaboration(models.Model):
    """Post muallifi yaqinlaridan 3 tagacha hammuallif taklifi."""

    class Status(models.TextChoices):
        PENDING = "pending", "Kutilmoqda"
        ACCEPTED = "accepted", "Qabul qilingan"
        DECLINED = "declined", "Rad etilgan"

    post_owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="collab_posts_owned", db_index=True
    )
    post_id = models.PositiveIntegerField(db_index=True)
    collaborator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="collab_posts_invited", db_index=True
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["post_owner", "post_id", "collaborator"],
                name="uniq_collab_post_collaborator",
            ),
        ]
        indexes = [
            models.Index(fields=["collaborator", "status"]),
        ]

    def __str__(self) -> str:
        return f"post {self.post_owner_id}/{self.post_id} + {self.collaborator_id} ({self.status})"


class Comment(models.Model):
    """Post izohi (post muallifining sqlite post_id si bilan bog‘langan)."""

    post_owner = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="post_comments_received", db_index=True
    )
    post_id = models.PositiveIntegerField(db_index=True)
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="post_comments_written", db_index=True
    )
    body = models.TextField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["post_owner", "post_id"]),
            models.Index(fields=["post_owner", "post_id", "created_at"]),
            models.Index(fields=["author", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.author_id} on {self.post_owner_id}/{self.post_id}"


class FeedPostSeen(models.Model):
    """Lentada post «to‘liq ko‘rilgan» deb belgilanguncha qayta chiqarish uchun."""

    viewer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="feed_posts_seen", db_index=True
    )
    post_author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="feed_seen_as_author", db_index=True
    )
    post_id = models.PositiveIntegerField()
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["viewer", "post_author", "post_id"],
                name="uniq_feed_seen_viewer_author_post",
            ),
        ]
        indexes = [
            models.Index(fields=["viewer", "post_author"]),
        ]

    def __str__(self) -> str:
        return f"{self.viewer_id} saw {self.post_author_id}/{self.post_id}"


class DMThread(models.Model):
    """
    Suhbat juftligi indeksi (inbox). Haqiqiy xabarlar alohida SQLite da: message_dbs/dm.<low>_<high>.sqlite3
    user_low_id doim user_high_id dan kichik bo‘ladi.
    """

    user_low = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="dm_threads_as_low",
        db_index=True,
    )
    user_high = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="dm_threads_as_high",
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)
    last_preview = models.CharField(max_length=140, blank=True, default="")
    last_sender = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    unread_for_low = models.PositiveIntegerField(default=0)
    unread_for_high = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user_low", "user_high"], name="uniq_dm_thread_pair"),
        ]
        indexes = [
            models.Index(fields=["user_low", "-updated_at"]),
            models.Index(fields=["user_high", "-updated_at"]),
        ]

    def __str__(self) -> str:
        return f"DM {self.user_low_id}↔{self.user_high_id}"

    def save(self, *args, **kwargs):
        if self.user_low_id and self.user_high_id and self.user_low_id >= self.user_high_id:
            raise ValueError("DMThread: user_low_id must be < user_high_id")
        super().save(*args, **kwargs)

    def peer_for(self, user: "User") -> "User":
        if user.id == self.user_low_id:
            return self.user_high
        if user.id == self.user_high_id:
            return self.user_low
        raise ValueError("user not in thread")

    def clear_unread_for(self, user: "User") -> None:
        if user.id == self.user_low_id:
            self.unread_for_low = 0
        elif user.id == self.user_high_id:
            self.unread_for_high = 0
        else:
            raise ValueError("user not in thread")

    def bump_unread_for_recipient(self, sender: "User") -> None:
        if sender.id == self.user_low_id:
            self.unread_for_high += 1
        elif sender.id == self.user_high_id:
            self.unread_for_low += 1
        else:
            raise ValueError("sender not in thread")
