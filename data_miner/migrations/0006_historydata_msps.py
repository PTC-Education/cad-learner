# Generated by Django 4.1.7 on 2023-04-10 19:54

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('data_miner', '0005_alter_historydata_final_query_complete_time_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='HistoryData_MSPS',
            fields=[
                ('historydata_ptr', models.OneToOneField(auto_created=True, on_delete=django.db.models.deletion.CASCADE, parent_link=True, primary_key=True, serialize=False, to='data_miner.historydata')),
                ('step_completion_time', models.JSONField(default=list, help_text='Time of submission of every completed step of the question', null=True)),
                ('step_feature_lists', models.JSONField(default=list, help_text='Correctly submitted feature lists of every step', null=True)),
                ('step_shaded_views', models.JSONField(default=list, help_text='Shaded view images of the correctly submitted model after every step', null=True)),
            ],
            bases=('data_miner.historydata',),
        ),
    ]