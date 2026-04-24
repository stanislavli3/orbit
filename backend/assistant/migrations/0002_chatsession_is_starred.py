from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="chatsession",
            name="is_starred",
            field=models.BooleanField(default=False),
        ),
    ]
