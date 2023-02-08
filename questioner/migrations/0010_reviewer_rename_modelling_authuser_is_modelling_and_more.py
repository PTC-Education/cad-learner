# Generated by Django 4.1.3 on 2023-02-03 16:44

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questioner', '0009_merge_20230130_1707'),
    ]

    operations = [
        migrations.CreateModel(
            name='Reviewer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('os_user_id', models.CharField(default=None, max_length=30, unique=True)),
                ('user_name', models.CharField(default=None, max_length=500, unique=True)),
                ('is_main_admin', models.BooleanField(default=False)),
            ],
        ),
        migrations.RenameField(
            model_name='authuser',
            old_name='modelling',
            new_name='is_modelling',
        ),
        migrations.RenameField(
            model_name='question',
            old_name='published',
            new_name='is_published',
        ),
        migrations.AddField(
            model_name='authuser',
            name='is_reviewer',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='question',
            name='reviewer_completion_count',
            field=models.PositiveIntegerField(default=0, help_text='The number of times this question is completed by reviewers'),
        ),
    ]