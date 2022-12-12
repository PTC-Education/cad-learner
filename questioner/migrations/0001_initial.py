# Generated by Django 4.1.3 on 2022-12-12 19:15

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='AuthUser',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('os_user_id', models.CharField(default=None, max_length=30, unique=True)),
                ('os_domain', models.URLField(max_length=100, null=True)),
                ('did', models.CharField(max_length=30, null=True)),
                ('wid', models.CharField(max_length=30, null=True)),
                ('eid', models.CharField(max_length=30, null=True)),
                ('access_token', models.CharField(max_length=100, null=True)),
                ('refresh_token', models.CharField(max_length=100, null=True)),
                ('expires_at', models.DateTimeField(null=True)),
                ('modelling', models.BooleanField(default=False)),
                ('last_start', models.DateTimeField(null=True)),
                ('curr_question', models.CharField(max_length=400, null=True)),
                ('start_microversion_id', models.CharField(max_length=30, null=True)),
                ('completed_history', models.JSONField(default=dict)),
            ],
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('question_id', models.BigAutoField(primary_key=True, serialize=False)),
                ('os_doc_id', models.CharField(default=None, help_text='Only relevant for initial save and model update', max_length=40, verbose_name='Onshape document ID')),
                ('os_workspace_id', models.CharField(default=None, help_text='Only relevant for initial save and model update', max_length=40, verbose_name='Onshape workspace ID')),
                ('os_element_id', models.CharField(default=None, help_text='Only relevant for initial save and model update', max_length=40, verbose_name='Onshape element ID')),
                ('cad_drawing', models.CharField(help_text='Insert single PDF file in GitHub repository and enter file name here (without .pdf suffix)', max_length=200, null=True, unique=True, verbose_name='File name of CAD drawing')),
                ('completion_count', models.PositiveIntegerField(default=0, help_text='The number of times this question is completed by users')),
                ('completion_time', models.JSONField(default=list, help_text='List of completion time by users in history')),
                ('question_name', models.CharField(help_text='A unique name for the question that will be displayed to the users', max_length=400, null=True, unique=True)),
                ('additional_instructions', models.TextField(blank=True, default=None, help_text='(Opitonal) additional instructions for users', null=True)),
                ('difficulty', models.PositiveIntegerField(default=0, help_text='Difficulty level of the model: 0 - unclassified, 1 - easy, 2 - medium, 3 - hard')),
                ('thumbnail', models.TextField(null=True)),
                ('model_mass', models.FloatField(null=True)),
                ('model_volume', models.FloatField(null=True)),
                ('model_SA', models.FloatField(help_text='Surface area', null=True)),
                ('published', models.BooleanField(default=False, help_text='Users can only access the model after it is published')),
            ],
        ),
    ]
