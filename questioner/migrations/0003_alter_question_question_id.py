# Generated by Django 4.1.3 on 2022-12-06 14:16

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questioner', '0002_alter_question_additional_instructions'),
    ]

    operations = [
        migrations.AlterField(
            model_name='question',
            name='question_id',
            field=models.BigAutoField(primary_key=True, serialize=False),
        ),
    ]
