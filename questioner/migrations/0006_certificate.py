# Generated by Django 4.2 on 2024-06-10 19:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('questioner', '0005_alter_authuser_completed_history_alter_authuser_did_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='Certificate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('certificate_name', models.CharField(help_text='A unique name for the certificate that will be displayed to the users', max_length=400, null=True, unique=True)),
                ('required_challenges', models.JSONField(default=list, help_text="An array (i.e. [4,12,23]) of the unique challenge id's required for certificate", null=True)),
                ('did', models.CharField(default=None, max_length=40, verbose_name='Onshape document ID')),
                ('vid', models.CharField(default=None, max_length=40, verbose_name='Onshape version ID')),
                ('jpeg_eid', models.CharField(default=None, help_text='Element ID for JPEG of certificate template', max_length=40, verbose_name='Onshape JPEG element ID')),
                ('drawing_eid', models.CharField(default=None, help_text='Element ID for drawing template of certificate', max_length=40, verbose_name='Onshape Drawing Template element ID')),
                ('drawing_jpeg', models.TextField(help_text='The exported JPEG image of the question stored as a base64 JPEG image', null=True)),
            ],
        ),
    ]
