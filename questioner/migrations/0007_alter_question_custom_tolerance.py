# Generated by Django 4.2 on 2024-06-03 19:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questioner', '0006_question_custom_tolerance'),
    ]

    operations = [
        migrations.AlterField(
            model_name='question',
            name='custom_tolerance',
            field=models.DecimalField(decimal_places=4, default=0.005, help_text='Input custom tolerance for challenge (input in decimal percent - default is 0.005)', max_digits=5, verbose_name='Custom tolerance for challenge (decimal percent - default is 0.005)'),
        ),
    ]
