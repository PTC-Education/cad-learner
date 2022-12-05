import os 
import requests
import datetime

from django.db import models
from django.utils import timezone

# Create your models here.
class AuthUser(models.Model): 
    os_user_id = models.CharField(max_length=30, default=None, unique=True)
    
    os_domain = models.URLField(max_length=100, null=True)
    did = models.CharField(max_length=30, null=True)
    wid = models.CharField(max_length=30, null=True)
    eid = models.CharField(max_length=30, null=True)

    access_token = models.CharField(max_length=100, null=True)
    refresh_token = models.CharField(max_length=100, null=True)
    expires_at = models.DateTimeField(null=True)

    modelling = models.BooleanField(default=False)
    last_start = models.DateTimeField(null=True) # only if modelling 
    curr_question = models.CharField(max_length=400, null=True) # only if modelling 
    completed = models.JSONField(default=list)

    def refresh_oauth_token(self) -> None: 
        response = requests.post(
            os.path.join(
                os.environ['OAUTH_URL'], 
                "oauth/token"
            ) + "?grant_type=refresh_token&refresh_token={}&client_id={}&client_secret={}".format(
                self.refresh_token.replace('=', '%3D'), 
                os.environ['OAUTH_CLIENT_ID'].replace('=', '%3D'), 
                os.environ['OAUTH_CLIENT_SECRET'].replace('=', '%3D')
            ), 
            headers={'Content-Type': "application/x-www-form-urlencoded"}
        )
        response = response.json() 

        self.access_token = response['access_token']
        self.refresh_token = response['refresh_token']
        self.expires_at = timezone.now() + datetime.timedelta(seconds=response['expires_in'])
        self.save() 
        return None 

    def __str__(self) -> str:
        return self.os_user_id


class Question(models.Model): 
    """ Every CAD modelling problem provided in the app 
    To add a new question, you must do the following in order:
    1.  Add the CAD drawing in one single PDF to the drawings folder 
    2.  Make sure an API key pair is provided in the Heroku configs 
        (need to be found in os.environ)
    3.  Use the admin portal to add the IDs to retrieve Onshape data 
    4.  Provide the file name of the drawings to be linked on the 
        admin portal 
    5.  Modify other parameters of the question on the admin portal if 
        needed 
    """
    # There is an auto-generated id for every question  

    # IDs used for initial save 
    os_doc_id = models.CharField(max_length=40, default=None)
    os_workspace_id = models.CharField(max_length=40, default=None)
    os_element_id = models.CharField(max_length=40, default=None)

    # Drawing needs to be first saved in the drawings directory
    cad_drawing = models.CharField(max_length=200, null=True)  # file name 
    # Number of people completed this question 
    completion_count = models.PositiveIntegerField(default=0)

    # Admin-specified parameters for the question 
    question_name = models.CharField(max_length=400, null=True, unique=True)
    additional_instructions = models.TextField(null=True)
    difficulty = models.PositiveIntegerField(default=0)
    # difficulty: 0 - unclassified, 1 - easy, 2 - medium, 3 - hard

    # API-retrieved info 
    thumbnail = models.TextField(null=True)
    model_mass = models.FloatField(null=True)
    model_volume = models.FloatField(null=True)
    model_SA = models.FloatField(null=True)
    model_COM_x = models.FloatField(null=True)
    model_COM_y = models.FloatField(null=True)
    model_COM_z = models.FloatField(null=True)

    # This boolean indicates when the system check is passed 
    published = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.question_name 

    def publish(self) -> None: 
        if self.published: 
            self.published = False 
        else: 
            # Check if necessary information is present and PDF is linked 
            if (
                self.question_name and self.cad_drawing and self.thumbnail and 
                self.model_mass and self.model_volume and self.model_SA and 
                self.model_COM_x and self.model_COM_y and self.model_COM_z
            ) and (
                os.path.isfile("drawings/{}.pdf".format(self.cad_drawing))
            ): 
                self.published = True 
        self.save() 
        return None 

    def get_updated_model(self) -> None: 
        # TODO: better authentication method pending for API calls 
        API_KEY = (os.environ['ADMIN_ACCESS'], os.environ['ADMIN_SECRET']) 

        # Get thumbnail 
        response = requests.get(
            "https://cad.onshape.com/api/partstudios/d/{}/w/{}/e/{}/shadedviews".format(
                self.os_doc_id, self.os_workspace_id, self.os_element_id
            ), 
            params={
                "outputHeight": 60, 
                "outputWidth": 60, 
                "pixelSize": 0, 
                "viewMatrix": "0.612,0.612,0,0,-0.354,0.354,0.707,0,0.707,-0.707,0.707,0"
            }, 
            headers={
                "Content-Type": "application/json", 
                "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09"
            }, 
            auth=API_KEY
        )
        
        if response.ok: 
            response = response.json() 
            self.thumbnail = f"data:image/png;base64,{response['images'][0]}"
        else: 
            self.thumbnail = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABmJLR0QA/wD/AP+gvaeTAAAAy0lEQVRIie2VXQ6CMBCEP7yDXkEjeA/x/icQgrQcAh9czKZ0qQgPRp1kk4ZZZvYnFPhjJi5ABfRvRgWUUwZLxIe4asEsMOhndmzhqbtZSdDExxh0EhacRBIt46V5oJDwEd4BuYQjscc90ATiJ8UfgFvEXPNNqotCKtEvF8HZS87wLAeOijeRTwhahsNoWmVi4pWRhLweqe4qCp1kLVUv3UX4VgtaX7IXbmsU0knuzuCz0SEwWIovvirqFTSrKbLkcZ8v+RecVyjyl3AHdAl3ObMLisAAAAAASUVORK5CYII="

        # Get mass and geometry properties 
        response = requests.get(
            "https://cad.onshape.com/api/partstudios/d/{}/w/{}/e/{}/massproperties".format(
                self.os_doc_id, self.os_workspace_id, self.os_element_id
            ), 
            headers={
                "Content-Type": "application/json", 
                "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09"
            }, 
            auth=API_KEY
        )
        if response.ok: 
            response = response.json() 
            self.model_mass = response['bodies']['-all-']['mass'][0]
            self.model_volume = response['bodies']['-all-']['volume'][0]
            self.model_SA = response['bodies']['-all-']['periphery'][0]
            self.model_COM_x = response['bodies']['-all-']['centroid'][0]
            self.model_COM_y = response['bodies']['-all-']['centroid'][1]
            self.model_COM_z = response['bodies']['-all-']['centroid'][2]
        else: 
            self.model_mass = None 
            self.model_volume = None
            self.model_SA = None
            self.model_COM_x = None
            self.model_COM_y = None
            self.model_COM_z = None

        self.save() 
        return None 
    
    def save(self, *args, **kwargs): 
        if not self.thumbnail or not self.model_mass: 
            self.get_updated_model() 
        return super().save(*args, **kwargs)