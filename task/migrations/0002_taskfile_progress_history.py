# Generated migration for adding progress_history field

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('task', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='taskfile',
            name='progress_history',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
