# Generated by Django 4.1.3 on 2022-12-08 18:23

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questioner', '0005_alter_question_additional_instructions'),
    ]

    operations = [
        migrations.AddField(
            model_name='question',
            name='completion_time',
            field=models.JSONField(default=list, help_text='List of completion time by users in history'),
        ),
        migrations.AlterField(
            model_name='authuser',
            name='completed_history',
            field=models.JSONField(default=dict),
        ),
    ]
