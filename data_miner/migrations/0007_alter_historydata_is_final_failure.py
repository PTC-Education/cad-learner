# Generated by Django 4.2 on 2023-05-05 15:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('data_miner', '0006_historydata_msps'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historydata',
            name='is_final_failure',
            field=models.BooleanField(default=True, help_text='Did final sub fail?'),
        ),
    ]
