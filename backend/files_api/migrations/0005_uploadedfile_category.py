from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("files_api", "0004_fileembedding"),
    ]

    operations = [
        migrations.AddField(
            model_name="uploadedfile",
            name="category",
            field=models.CharField(
                choices=[("vault", "Vault"), ("library", "Library")],
                default="vault",
                max_length=20,
            ),
        ),
    ]
