# Generated by Django 4.1.7 on 2023-03-30 17:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questioner', '0003_alter_question_is_collecting_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='question_mpps',
            name='model_name',
            field=models.JSONField(default=list, help_text='Part names', null=True),
        ),
        migrations.AddField(
            model_name='question_step_ps',
            name='model_name',
            field=models.JSONField(default=list, help_text='Part names', null=True),
        ),
    ]
