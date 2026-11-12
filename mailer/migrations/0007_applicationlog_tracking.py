# Generated manually for safe unique UUID population

import uuid
from django.db import migrations, models


def populate_unique_tracking_tokens(apps, schema_editor):
    ApplicationLog = apps.get_model('mailer', 'ApplicationLog')
    for log in ApplicationLog.objects.all():
        log.tracking_token = uuid.uuid4()
        log.save(update_fields=['tracking_token'])


class Migration(migrations.Migration):

    dependencies = [
        ('mailer', '0006_applicationlog_message_id_followupsequence'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicationlog',
            name='tracking_token',
            field=models.UUIDField(default=uuid.uuid4, null=True, help_text='Unique UUIDv4 token for open and click telemetry'),
        ),
        migrations.AddField(
            model_name='applicationlog',
            name='opened_at',
            field=models.DateTimeField(blank=True, null=True, help_text='Timestamp when email was first opened'),
        ),
        migrations.AddField(
            model_name='applicationlog',
            name='open_count',
            field=models.PositiveIntegerField(default=0, help_text='Total number of times email was opened'),
        ),
        migrations.AddField(
            model_name='applicationlog',
            name='clicked_at',
            field=models.DateTimeField(blank=True, null=True, help_text='Timestamp when a project link was first clicked'),
        ),
        migrations.AddField(
            model_name='applicationlog',
            name='click_count',
            field=models.PositiveIntegerField(default=0, help_text='Total number of times links were clicked'),
        ),
        migrations.RunPython(populate_unique_tracking_tokens, reverse_code=migrations.RunPython.noop),
        migrations.AlterField(
            model_name='applicationlog',
            name='tracking_token',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True, help_text='Unique UUIDv4 token for open and click telemetry'),
        ),
        migrations.AddIndex(
            model_name='applicationlog',
            index=models.Index(fields=['tracking_token'], name='idx_applog_tracking'),
        ),
        migrations.AddIndex(
            model_name='applicationlog',
            index=models.Index(fields=['opened_at', 'clicked_at'], name='idx_applog_engagement'),
        ),
    ]
