from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('residents', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='resident',
            name='is_indigent',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='resident',
            name='is_solo_parent',
            field=models.BooleanField(default=False),
        ),
    ]
