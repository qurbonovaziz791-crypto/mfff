from __future__ import annotations

from django.apps import apps
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from blogs.storage import init_user_db


@receiver(post_save)
def ensure_user_db(sender, instance, created, **kwargs):
    """
    Yangi user yaratilganda (register) uning uchun alohida sqlite db yaratadi:
    `user_dbs/db.<username>.sqlite3`
    """
    UserModel = apps.get_model("users", "User")
    if sender is not UserModel:
        return
    if created:
        init_user_db(instance.id, username=instance.username)


@receiver(pre_save)
def _capture_old_verified(sender, instance, **kwargs):
    UserModel = apps.get_model("users", "User")
    if sender is not UserModel:
        return
    if not getattr(instance, "pk", None):
        return
    old = (
        UserModel.objects.filter(pk=instance.pk)
        .only("id", "is_verified")
        .values_list("is_verified", flat=True)
        .first()
    )
    instance._old_is_verified = old


@receiver(post_save)
def notify_verified_change(sender, instance, created, **kwargs):
    UserModel = apps.get_model("users", "User")
    if sender is not UserModel:
        return
    if created:
        return
    old = getattr(instance, "_old_is_verified", None)
    if old is None:
        return
    new = bool(getattr(instance, "is_verified", False))
    if bool(old) == new:
        return
    try:
        from users import tasks as user_tasks

        user_tasks.create_notification.delay(
            user_id=int(instance.pk),
            kind="verified_change",
            payload={"is_verified": bool(new), "source": "admin"},
        )
    except Exception:
        pass


def ensure_all_users_dbs() -> None:
    """
    Server ishga tushganda mavjud barcha userlar uchun ham db fayllarni yaratib chiqadi.
    (Idempotent: mavjud bo'lsa, qayta yaratmaydi.)
    """
    UserModel = apps.get_model("users", "User")
    for u in UserModel.objects.only("id", "username").iterator():
        init_user_db(u.id, username=u.username)

