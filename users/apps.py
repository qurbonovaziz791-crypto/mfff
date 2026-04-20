from django.apps import AppConfig
from django.db.models.signals import post_migrate


class UsersConfig(AppConfig):
    name = 'users'

    def ready(self):
        # Signal registration
        from . import signals  # noqa: F401

        # App init vaqtida DBga tegish (ready()) Django tomonidan tavsiya etilmaydi.
        # Mavjud userlar uchun db fayllarni migratsiyadan keyin (safe point) yaratamiz.
        def _on_post_migrate(**kwargs):
            try:
                signals.ensure_all_users_dbs()
            except Exception:
                # Startup'ni yiqitmaslik uchun
                pass

        post_migrate.connect(_on_post_migrate, sender=self)
