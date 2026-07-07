from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0012_blogpost_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='LabResult',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('test_name', models.CharField(max_length=150)),
                ('result_value', models.CharField(max_length=100)),
                ('unit', models.CharField(blank=True, max_length=50)),
                ('reference_range', models.CharField(blank=True, max_length=100)),
                ('collected_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lab_results', to='patients.patient')),
            ],
            options={
                'ordering': ['-collected_at'],
                'indexes': [models.Index(fields=['patient'], name='patients_la_patient_b3635d_idx'), models.Index(fields=['collected_at'], name='patients_la_collect_91af4b_idx')],
            },
        ),
    ]