from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_userprofile_is_philsys_verified_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="userprofile",
            name="middle_name",
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
