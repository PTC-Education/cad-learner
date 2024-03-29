# Generated by Django 4.1.7 on 2023-04-04 19:19

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('questioner', '0004_question_mpps_model_name_question_step_ps_model_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='authuser',
            name='completed_history',
            field=models.JSONField(default=dict, help_text='Question completion history of the user'),
        ),
        migrations.AlterField(
            model_name='authuser',
            name='did',
            field=models.CharField(help_text='Onshape document ID', max_length=30, null=True),
        ),
        migrations.AlterField(
            model_name='authuser',
            name='eid',
            field=models.CharField(help_text='Onshape element ID', max_length=30, null=True),
        ),
        migrations.AlterField(
            model_name='authuser',
            name='end_mid',
            field=models.CharField(help_text='Onshape microversion ID of the last submission attempt (could be either successful or failure)', max_length=30, null=True),
        ),
        migrations.AlterField(
            model_name='authuser',
            name='etype',
            field=models.CharField(choices=[('N/A', 'Not Applicable'), ('partstudios', 'Part Studio'), ('assemblies', 'Assembly'), ('all', 'All Types')], help_text='Onshape element type', max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='authuser',
            name='failure_history',
            field=models.JSONField(default=dict, help_text='Question failure history of the user'),
        ),
        migrations.AlterField(
            model_name='authuser',
            name='is_reviewer',
            field=models.BooleanField(default=False, help_text='Set through the Reviewer model'),
        ),
        migrations.AlterField(
            model_name='authuser',
            name='last_start',
            field=models.DateTimeField(help_text='Last time the quesiton was initiated', null=True),
        ),
        migrations.AlterField(
            model_name='authuser',
            name='os_domain',
            field=models.URLField(help_text='https://cad.onshape.com for non-enterprise Onshape accounts', max_length=100, null=True),
        ),
        migrations.AlterField(
            model_name='authuser',
            name='start_mid',
            field=models.CharField(help_text='Onshape microversion ID when the question is first initiated', max_length=30, null=True),
        ),
        migrations.AlterField(
            model_name='authuser',
            name='wid',
            field=models.CharField(help_text='Onshape workspace ID', max_length=30, null=True),
        ),
        migrations.AlterField(
            model_name='question',
            name='allowed_etype',
            field=models.CharField(choices=[('N/A', 'Not Applicable'), ('partstudios', 'Part Studio'), ('assemblies', 'Assembly'), ('all', 'All Types')], default='all', help_text='Allowed Onshape element type(s) that this question can be started in', max_length=40, verbose_name='Allowed element type(s)'),
        ),
        migrations.AlterField(
            model_name='question',
            name='completion_time',
            field=models.JSONField(default=list, help_text='List of completion time spent (in seconds) by users in history'),
        ),
        migrations.AlterField(
            model_name='question',
            name='drawing_jpeg',
            field=models.TextField(help_text='The exported JPEG image of the question stored as a base64 JPEG image', null=True),
        ),
        migrations.AlterField(
            model_name='question',
            name='eid',
            field=models.CharField(default=None, help_text='The Onshape element ID that the thumbnail image will be taken from. It should capture the expected solution to the question', max_length=40, verbose_name='Onshape element ID'),
        ),
        migrations.AlterField(
            model_name='question',
            name='is_collecting_data',
            field=models.BooleanField(default=False, help_text='User design data is only collected when this is set to be True, assuming the question is published'),
        ),
        migrations.AlterField(
            model_name='question',
            name='is_published',
            field=models.BooleanField(default=False, help_text='Users can only access the model and user data will only be recorded after it is published'),
        ),
        migrations.AlterField(
            model_name='question',
            name='jpeg_drawing_eid',
            field=models.CharField(help_text="Element ID of an exported JPEG image of the question's drawing, stored as an Onshape element in the same question document (portrait rather than landscape is preferred)", max_length=40, null=True, verbose_name='Onshape element ID of a JPEG export of a drawing'),
        ),
        migrations.AlterField(
            model_name='question',
            name='os_drawing_eid',
            field=models.CharField(help_text='Element ID of the native Onshape drawing that users can open in a new tab', max_length=40, null=True, verbose_name='Onshape element ID of the main Onshape drawing'),
        ),
        migrations.AlterField(
            model_name='question',
            name='question_id',
            field=models.BigAutoField(help_text='An auto-generated incremental unique ID for every question added', primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='question',
            name='thumbnail',
            field=models.TextField(help_text='The thumbnail image of the question stored as a base64 PNG image', null=True),
        ),
        migrations.AlterField(
            model_name='question_asmb',
            name='completion_feature_cnt',
            field=models.JSONField(default=list, help_text='List of mate feature counts required by users to complete the question in history'),
        ),
        migrations.AlterField(
            model_name='question_asmb',
            name='model_inertia',
            field=models.JSONField(default=list, help_text='An ordered list of 3 principal interia in kg.m^2', null=True),
        ),
        migrations.AlterField(
            model_name='question_asmb',
            name='starting_eid',
            field=models.CharField(default=None, help_text='Starting part studio with parts that need to be imported to user assembly as part instances to be assembled', max_length=40, null=True, verbose_name='Source Part Studio element ID'),
        ),
        migrations.AlterField(
            model_name='question_mpps',
            name='completion_feature_cnt',
            field=models.JSONField(default=list, help_text='List of feature counts required by users to complete the question in history'),
        ),
        migrations.AlterField(
            model_name='question_mpps',
            name='init_mid',
            field=models.CharField(default=None, help_text="Last microversion of the starting element's version, required for derived import if a starting part studio is used", max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='question_mpps',
            name='model_inertia',
            field=models.JSONField(default=list, help_text='List of ordered list of 3 principal interia in kg.m^2', null=True),
        ),
        migrations.AlterField(
            model_name='question_mpps',
            name='ref_mid',
            field=models.CharField(default=None, help_text="Last microversion of the reference element's version, required for derived import", max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='question_msps',
            name='completion_feature_cnt',
            field=models.JSONField(default=list, help_text='List of feature counts required by users to complete the question in history'),
        ),
        migrations.AlterField(
            model_name='question_msps',
            name='init_mid',
            field=models.CharField(default=None, help_text="Last microversion of the starting element's version, required for derived import if a starting part studio is used", max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='question_msps',
            name='starting_eid',
            field=models.CharField(blank=True, default=None, help_text='(Optional) Starting Part Studio that needs to be imported to user document with derived features (leave blank if none is required)', max_length=40, null=True, verbose_name='Starting element ID'),
        ),
        migrations.AlterField(
            model_name='question_spps',
            name='completion_feature_cnt',
            field=models.JSONField(default=list, help_text='List of feature counts required by users to complete the question in history'),
        ),
        migrations.AlterField(
            model_name='question_spps',
            name='model_inertia',
            field=models.JSONField(default=list, help_text='An ordered list of 3 principal interia in kg.m^2', null=True),
        ),
        migrations.AlterField(
            model_name='question_spps',
            name='ref_mid',
            field=models.CharField(default=None, help_text="Last microversion of the reference element's version, required for derived import", max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='question_step_ps',
            name='drawing_jpeg',
            field=models.TextField(help_text='The exported JPEG image of the question stored as a base64 JPEG image', null=True),
        ),
        migrations.AlterField(
            model_name='question_step_ps',
            name='eid',
            field=models.CharField(default=None, help_text='The Onshape element with the reference model', max_length=40, verbose_name='Onshape element ID'),
        ),
        migrations.AlterField(
            model_name='question_step_ps',
            name='jpeg_drawing_eid',
            field=models.CharField(help_text="Element ID of an exported JPEG image of the question's drawing, stored as an Onshape element in the same question document (portrait rather than landscape is preferred); this can be the same ID to the one used for the question or other steps if the same drawing is used", max_length=40, null=True, verbose_name='JPEG drawing element ID of the step'),
        ),
        migrations.AlterField(
            model_name='question_step_ps',
            name='mid',
            field=models.CharField(default=None, help_text="Last microversion of the reference element's version, required for derive import", max_length=40, null=True),
        ),
        migrations.AlterField(
            model_name='question_step_ps',
            name='model_inertia',
            field=models.JSONField(default=list, help_text='(List of) ordered list of 3 principal interia in kg.m^2', null=True),
        ),
        migrations.AlterField(
            model_name='question_step_ps',
            name='os_drawing_eid',
            field=models.CharField(help_text='Element ID of the native Onshape drawing that users can open in a new tab; this can be the same ID to the one used for the question or other steps if the same drawing is used', max_length=40, null=True, verbose_name='Onshape drawing element ID of the step'),
        ),
        migrations.AlterField(
            model_name='question_step_ps',
            name='question',
            field=models.ForeignKey(help_text='The parent MSPS question', on_delete=django.db.models.deletion.CASCADE, to='questioner.question_msps'),
        ),
        migrations.AlterField(
            model_name='question_step_ps',
            name='step_number',
            field=models.PositiveIntegerField(default=1, help_text='Positive step number of the question (index starts from 1)'),
        ),
        migrations.AlterField(
            model_name='reviewer',
            name='is_active',
            field=models.BooleanField(default=True, help_text='Inactive reviewers do not see unpublished questions'),
        ),
        migrations.AlterField(
            model_name='reviewer',
            name='is_main_admin',
            field=models.BooleanField(default=False, help_text='All Onshape API calls initiated through the admin portal (e.g., when questions are added or updated) will be made with the ``access_token`` of the main admin'),
        ),
        migrations.AlterField(
            model_name='reviewer',
            name='user_name',
            field=models.CharField(default=None, help_text="User name used for the user's Onshape account", max_length=500, unique=True),
        ),
    ]
