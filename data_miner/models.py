from django.db import models

# Create your models here.
class HistoryData(models.Model): 
    os_user_id = models.CharField(max_length=30, default=None)
    question_id = models.IntegerField(default=0) 
    question_name = models.CharField(max_length=400, default=None)
    completion_time = models.DateTimeField(auto_now=True)
    num_attempt = models.IntegerField(default=0) # the n-th attempt 
    time_spent = models.FloatField(default=0.0)

    microversions = models.JSONField(default=list, null=True)
    feature_list = models.JSONField(default=dict, null=True)
    fs_representation = models.JSONField(default=dict, null=True)
    mesh_data = models.JSONField(default=list, null=True)

    # Since all design data are queried in the background after a task 
    # is completed, the time a user completes the task and the time the 
    # app completes all the data retrieval are likely different. 
    # This field tracks the latter time for open-sourced database update 
    # purpose. 
    query_complete_time = models.DateTimeField(default=None, null=True)