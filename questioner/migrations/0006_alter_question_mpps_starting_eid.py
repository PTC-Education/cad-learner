# Generated by Django 4.1.3 on 2023-01-25 18:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questioner', '0005_remove_question_wid_authuser_add_field_question_vid_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='question_mpps',
            name='starting_eid',
            field=models.CharField(default=None, help_text='(Optional) Starting part studio that need to be imported to user document with derived features. Leave blank if none is required.', max_length=40, null=True, verbose_name='Starting element ID'),
        ),
    ]