from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('residents', '0001_initial'),
        ('certifications', '0002_initial'),
        migrations.swappable_dependency('core.User'),
    ]

    operations = [
        migrations.CreateModel(
            name='OfficialReceipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('or_number', models.CharField(max_length=50, unique=True, verbose_name='OR Number')),
                ('resident_name', models.CharField(max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('particulars', models.TextField(help_text='Description of what is being paid for (e.g. Barangay Clearance)')),
                ('issued_at', models.DateTimeField(auto_now_add=True)),
                ('issued_by', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='issued_receipts', to='core.user')),
            ],
            options={
                'verbose_name': 'Official Receipt',
                'verbose_name_plural': 'Official Receipts',
                'ordering': ['-issued_at'],
            },
        ),
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('method', models.CharField(choices=[('cash', 'Cash at Hall'), ('gcash', 'GCash'), ('waived', 'Waived')], default='cash', max_length=20)),
                ('status', models.CharField(choices=[('unpaid', 'Unpaid'), ('pending', 'Pending Verification'), ('paid', 'Paid'), ('waived', 'Waived')], default='unpaid', max_length=20)),
                ('amount', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('proof_screenshot', models.ImageField(blank=True, null=True, upload_to='payments/proofs/')),
                ('gcash_ref_number', models.CharField(blank=True, max_length=100, null=True, verbose_name='GCash Reference Number')),
                ('waive_reason', models.TextField(blank=True, null=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('official_receipt', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payment_record', to='payments.officialreceipt')),
                ('verified_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='verified_payments', to='core.user')),
            ],
            options={
                'verbose_name': 'Payment',
                'verbose_name_plural': 'Payments',
                'ordering': ['-created_at'],
            },
        ),
    ]
