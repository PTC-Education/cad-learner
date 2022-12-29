from django.db import models

# Create your models here.
class HistoryData(models.Model): 
    os_user_id = models.CharField(max_length=30, default=None)
    question_name = models.CharField(max_length=400, default=None)
    completion_time = models.DateTimeField(auto_now=True)
    num_attempt = models.IntegerField(default=0)

    microversions = models.JSONField(default=list, null=True)
    feature_list = models.JSONField(default=dict, null=True)
    fs_representation = models.JSONField(default=dict, null=True)
    shaded_views = models.JSONField(default=list, null=True)
    mesh_data = models.JSONField(default=list, null=True)