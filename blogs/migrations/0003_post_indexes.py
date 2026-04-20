from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("blogs", "0002_kayfiyat_alter_post_mood"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["author", "-created_at"], name="blogs_post_author_created_desc_idx"),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["author", "created_at"], name="blogs_post_author_created_idx"),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["hashtag"], name="blogs_post_hashtag_idx"),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(fields=["is_public", "-created_at"], name="blogs_post_public_created_desc_idx"),
        ),
    ]

