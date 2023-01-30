# Generated by Django 4.1.3 on 2022-12-29 16:45

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='HistoryData',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('os_user_id', models.CharField(default=None, max_length=30)),
                ('question_name', models.CharField(default=None, max_length=400)),
                ('completion_time', models.DateTimeField(auto_now=True)),
                ('num_attempt', models.IntegerField(default=0)),
                ('microversions', models.JSONField(default=list, null=True)),
                ('feature_list', models.JSONField(default=dict, null=True)),
                ('fs_representation', models.JSONField(default=dict, null=True)),
                ('shaded_views', models.JSONField(default=list, null=True)),
                ('mesh_data', models.JSONField(default=list, null=True)),
            ],
        ),
    ]
