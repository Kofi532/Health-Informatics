from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0011_prescription'),
    ]

    operations = [
        migrations.AddField(
            model_name='blogpost',
            name='category',
            field=models.CharField(
                choices=[
                    ('general', 'General Blog'),
                    ('dietician', 'Chat with a Dietician'),
                    ('nutritionnist', 'Chat with a Nutritionnist'),
                    ('pharmacist', 'Chat with a Pharmacist'),
                    ('physician', 'Chat with a Physician'),
                ],
                db_index=True,
                default='general',
                max_length=20,
            ),
        ),
    ]