from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0010_alter_notification_kind"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(fields=["post_owner", "post_id", "created_at"], name="users_comment_owner_post_created_idx"),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(fields=["author", "-created_at"], name="users_comment_author_created_desc_idx"),
        ),
    ]

