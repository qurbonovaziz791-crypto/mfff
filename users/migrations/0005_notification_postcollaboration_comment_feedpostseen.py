from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0004_yaqinrequest"),
    ]

    operations = [
        migrations.CreateModel(
            name="Notification",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("yaqin_request", "Yaqinlik so‘rovi"),
                            ("collab_invite", "Postga ulashish"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("read_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="notifications",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="PostCollaboration",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("post_id", models.PositiveIntegerField(db_index=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Kutilmoqda"),
                            ("accepted", "Qabul qilingan"),
                            ("declined", "Rad etilgan"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "collaborator",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="collab_posts_invited",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "post_owner",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="collab_posts_owned",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("post_id", models.PositiveIntegerField(db_index=True)),
                ("body", models.TextField(max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="post_comments_written",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "post_owner",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="post_comments_received",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="FeedPostSeen",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("post_id", models.PositiveIntegerField()),
                ("seen_at", models.DateTimeField(auto_now_add=True)),
                (
                    "post_author",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="feed_seen_as_author",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "viewer",
                    models.ForeignKey(
                        on_delete=models.CASCADE,
                        related_name="feed_posts_seen",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="postcollaboration",
            constraint=models.UniqueConstraint(
                fields=("post_owner", "post_id", "collaborator"),
                name="uniq_collab_post_collaborator",
            ),
        ),
        migrations.AddIndex(
            model_name="postcollaboration",
            index=models.Index(fields=["collaborator", "status"], name="users_postco_collabo_0a1b2c_idx"),
        ),
        migrations.AddIndex(
            model_name="comment",
            index=models.Index(fields=["post_owner", "post_id"], name="users_commen_post_ow_3d4e5f_idx"),
        ),
        migrations.AddConstraint(
            model_name="feedpostseen",
            constraint=models.UniqueConstraint(
                fields=("viewer", "post_author", "post_id"),
                name="uniq_feed_seen_viewer_author_post",
            ),
        ),
        migrations.AddIndex(
            model_name="feedpostseen",
            index=models.Index(fields=["viewer", "post_author"], name="users_feedpos_viewer_6g7h8i_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["user", "created_at"], name="users_notifi_user_created_idx"),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["user", "read_at"], name="users_notifi_user_id_2m3n4o_idx"),
        ),
    ]
