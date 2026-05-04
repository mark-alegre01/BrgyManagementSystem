from django.db import migrations, models
import django.db.models.deletion
import certifications.models

class Migration(migrations.Migration):

    dependencies = [
        ('certifications', '0002_initial'),
        ('payments', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificaterequest',
            name='payment',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='certificate_request', to='payments.payment'),
        ),
        migrations.AddField(
            model_name='certificaterequest',
            name='tracking_code',
            field=models.CharField(default=certifications.models.generate_tracking_code, max_length=20, unique=True),
        ),
    ]
