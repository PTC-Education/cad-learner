# Generated by Django 4.1.3 on 2022-12-09 19:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('questioner', '0006_question_completion_time_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='question',
            name='model_COM_x',
        ),
        migrations.RemoveField(
            model_name='question',
            name='model_COM_y',
        ),
        migrations.RemoveField(
            model_name='question',
            name='model_COM_z',
        ),
    ]
