from __future__ import annotations

from django.apps import apps
from django.db.models.signals import post_save
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


def ensure_all_users_dbs() -> None:
    """
    Server ishga tushganda mavjud barcha userlar uchun ham db fayllarni yaratib chiqadi.
    (Idempotent: mavjud bo'lsa, qayta yaratmaydi.)
    """
    UserModel = apps.get_model("users", "User")
    for u in UserModel.objects.only("id", "username").iterator():
        init_user_db(u.id, username=u.username)

