"""
Development Guide 
Last major structural update: Jan. 27, 2023

The Django model class "HistoryData" is a base parent class of all question types. 
Every question type should inheret the properties and methods of the HistoryData class. 

When new question types are created in the "questioner" app, a new HistoryData type 
should also be added. 
When creating new history data types: 
1. Add new HistoryData_{QuestionType} class to inheret the HistoryData class 
2. First add additional fields of data that are being tracked for the new 
   question type (and additional API helper functions if needed) 
3. Add two default methods to the new class: 
    (i).  first_failure_record(): get and record data for the first failed submission 
    (ii). final_sub_record(): get and record data for the final successful submission 
"""

import os 
import base64 
import requests 
import trimesh
from datetime import timedelta
from typing import Tuple, Dict, List, Any 

from django.db import models
from django.utils import timezone

from questioner.models import AuthUser, QuestionType


# Two isometric view matrices 
FRT_VIEW_MAT = [
    0.707, 0.707, 0., 0., 
    -0.408, 0.408, 0.816, 0.,
    0.577, -0.577, 0.577, 0.
] # captures front, right, top face 
BLB_VIEW_MAT = [
    -0.707, -0.707, 0., 0., 
    -0.408, 0.408, 0.816, 0.,
    -0.577, 0.577, -0.577, 0.
] # captures back, left, bottom face 


# Create your models here.
class HistoryData(models.Model): 
    """ 
    The base class for history data collection of all question types 
    
    It stores all the common fields, and each question type should have additional fields and methods added for different types of design data to be stored and collected 
    """
    # User identification  
    os_user_id = models.CharField(max_length=30, default=None)
    start_time = models.DateTimeField(
        default=None, null=True, help_text="Time the question was initiated for the user"
    )
    time_of_completion = models.DateTimeField(
        default=None, null=True, help_text="Time of the final submission of the question received, either successful or failed"
    )
    
    # Question identification 
    question_id = models.IntegerField(default=0, help_text='Unique question ID') 
    question_type = models.CharField(
        max_length=4, choices=QuestionType.choices, default=QuestionType.UNKNOWN
    )
    
    # Attempt information 
    num_attempt = models.IntegerField(default=0, help_text="The n-th attempt") 
    is_final_failure = models.BooleanField(default=True, help_text="Did final sub fail?")
    # General design data collected 
    # Each question type may collect additional design data 
    microversions_descrip = models.JSONField(
        default=list, null=True, help_text="Descriptions of all microversion history events (with user names removed)"
    )
    # Since all design data are queried in the background after a task 
    # is completed, the time a user completes the task and the time the 
    # app completes all the data retrieval are likely different. 
    # This field tracks the latter time for database update purpose. 
    final_query_complete_time = models.DateTimeField(
        default=None, null=True, help_text="Time when all data query API calls were completed"
    )

    def first_failure_record(self, user: AuthUser, q_info: Tuple[str]) -> None: 
        return None 

    def final_sub_record(self, user: AuthUser, q_info: Tuple[str]) -> None: 
        return None 


class HistoryData_PS(HistoryData): 
    """ 
    Inherits :model:`data_miner.HistoryData` and is used for both :model:`questioner.Question_SPPS` questions and :model:`questioner.Question_MPPS` questions 
    """
    # First failed submission 
    first_failed_time = models.DateTimeField(
        default=None, null=True, help_text="Time of the first failed submission"
    )
    failed_feature_list = models.JSONField(
        default=dict, null=True, help_text="Feature list of the first failed submission model"
    )
    failed_shaded_views = models.JSONField(
        default=dict, null=True, help_text="Shaded view images of the first failed submission model"
    )
    failed_mesh = models.TextField(
        default=None, null=True, blank=True, help_text="Mesh of the first failed submission model"
    )

    # Final submission 
    final_feature_list = models.JSONField(
        default=dict, null=True, help_text="Feature list of the final submitted model"
    )
    final_shaded_views = models.JSONField(
        default=dict, null=True, help_text="Shaded view images of the final submitted model"
    )
    process_mesh = models.JSONField(
        default=list, null=True, help_text="The mesh of the model after every feature of the final submitted model"
    ) # List[Tuple[rollbackBarIndex, mesh]]

    def first_failure_record(self, user: AuthUser, q_info: Tuple[str]) -> None: 
        """ 
        Record data for first failed submission 
        
        **Arguments:**
        
        - ``user``: the :model:`questioner.AuthUser` that stores all user-specific login info with accessing tokens
        - ``q_info``: ``Tuple[os_domain, did, begin_mid, end_mid, eid, etype]`` at the time of completion 
        """
        # Check if user's OAuth token still valid 
        if user.expires_at <= timezone.now() + timedelta(minutes=10): 
            user.refresh_oauth_token() 

        self.failed_feature_list = get_feature_list(user, q_info)
        self.failed_shaded_views = {
            "FRT": get_shaded_view(user, q_info, view_mat=FRT_VIEW_MAT), 
            "BLB": get_shaded_view(user, q_info, view_mat=BLB_VIEW_MAT)
        }
        self.failed_mesh = get_stl_mesh(user, q_info)
        self.final_query_complete_time = timezone.now() 
        self.save() 

    def final_sub_record(self, user: AuthUser, q_info: Tuple[str]) -> None: 
        """ 
        Record data for final submission, either successful or failed
        
        **Arguments:**
        
        - ``user``: the :model:`questioner.AuthUser` that stores all user-specific login info with accessing tokens
        - ``q_info``: ``Tuple[os_domain, did, begin_mid, end_mid, eid, etype]`` at the time of completion 
        """
        # Check if user's OAuth token still valid 
        if user.expires_at <= timezone.now() + timedelta(minutes=10): 
            user.refresh_oauth_token() 

        self.microversions_descrip = get_microversions_descrip(user, q_info)
        self.final_feature_list = get_feature_list(user, q_info)
        self.final_shaded_views = {
            "FRT": get_shaded_view(user, q_info, view_mat=FRT_VIEW_MAT), 
            "BLB": get_shaded_view(user, q_info, view_mat=BLB_VIEW_MAT)
        }
        self.process_mesh = [(-1, get_stl_mesh(user, q_info))]
        self.final_query_complete_time = timezone.now() 
        self.save() 


class HistoryData_AS(HistoryData): 
    """ 
    Inherits :model:`data_miner.HistoryData` and is used for both :model:`questioner.Question_ASMB` questions 
    """
    # First failed submission 
    first_failed_time = models.DateTimeField(
        default=None, null=True, help_text="Time of the first failed submission"
    )
    failed_assembly_def = models.JSONField(
        default=dict, null=True, help_text="Assembly definition of the first failed submission assembly"
    )
    failed_shaded_views = models.JSONField(
        default=dict, null=True, help_text="Shaded view images of the first failed submission assembly"
    )

    # Final submission 
    final_assembly_def = models.JSONField(
        default=dict, null=True, help_text="Assembly definition of the final submitted assembly"
    )
    final_shaded_views = models.JSONField(
        default=dict, null=True, help_text="Shaded view images of the final submitted assembly"
    )

    def first_failure_record(self, user: AuthUser, q_info: Tuple[str]) -> None: 
        """ 
        Record data for first failed submission 
        
        **Arguments:**
        
        - ``user``: the :model:`questioner.AuthUser` that stores all user-specific login info with accessing tokens
        - ``q_info``: ``Tuple[os_domain, did, begin_mid, end_mid, eid, etype]`` at the time of completion 
        """
        # Check if user's OAuth token still valid 
        if user.expires_at <= timezone.now() + timedelta(minutes=10): 
            user.refresh_oauth_token() 

        self.failed_feature_list = get_assembly_definition(user, q_info)
        self.failed_shaded_views = {
            "FRT": get_shaded_view(user, q_info, view_mat=FRT_VIEW_MAT), 
            "BLB": get_shaded_view(user, q_info, view_mat=BLB_VIEW_MAT)
        }
        self.final_query_complete_time = timezone.now() 
        self.save() 

    def final_sub_record(self, user: AuthUser, q_info: Tuple[str]) -> None: 
        """ 
        Record data for final submission, either successful or failed
        
        **Arguments:**
        
        - ``user``: the :model:`questioner.AuthUser` that stores all user-specific login info with accessing tokens
        - ``q_info``: ``Tuple[os_domain, did, begin_mid, end_mid, eid, etype]`` at the time of completion 
        """
        # Check if user's OAuth token still valid 
        if user.expires_at <= timezone.now() + timedelta(minutes=10): 
            user.refresh_oauth_token() 

        self.microversions_descrip = get_microversions_descrip(user, q_info)
        self.final_assembly_def = get_assembly_definition(user, q_info)
        self.final_shaded_views = {
            "FRT": get_shaded_view(user, q_info, view_mat=FRT_VIEW_MAT), 
            "BLB": get_shaded_view(user, q_info, view_mat=BLB_VIEW_MAT)
        }
        self.final_query_complete_time = timezone.now() 
        self.save() 


class HistoryData_MSPS(HistoryData): 
    """
    Inherits :model:`data_miner.HistoryData` and is used for both :model:`questioner.Question_MSPS` questions 
    
    Note: due to limit of storage space, only data of successful attempts (both steps and full questions) are recorded for :model:`questioner.Question_MSPS` questions 
    """
    step_completion_time = models.JSONField(
        default=list, null=True, help_text="Time of submission of every completed step of the question"
    )
    step_feature_lists = models.JSONField(
        default=list, null=True, help_text="Correctly submitted feature lists of every step"
    )
    step_shaded_views = models.JSONField(
        default=list, null=True, help_text="Shaded view images of the correctly submitted model after every step"
    )
    
    def collect_data(self, user: AuthUser, q_info: Tuple[str], is_final_step=False) -> None: 
        """
        Record data after correct submission of every step of the question 
        
        **Arguments:**
        
        - ``user``: the :model:`questioner.AuthUser` that stores all user-specific login info with accessing tokens
        - ``q_info``: ``Tuple[os_domain, did, begin_mid, end_mid, eid, etype]`` at the time of completion 
        - ``is_final_step``: if this is the final step of the multi-step question 
        """
        # Check if user's OAuth token still valid 
        if user.expires_at <= timezone.now() + timedelta(minutes=10): 
            user.refresh_oauth_token() 
        
        self.step_feature_lists.append(get_feature_list(user, q_info))
        self.step_shaded_views.append({
            "FRT": get_shaded_view(user, q_info, view_mat=FRT_VIEW_MAT), 
            "BLB": get_shaded_view(user, q_info, view_mat=BLB_VIEW_MAT)
        })
        self.final_query_complete_time = timezone.now() 
        
        # If final step of the question 
        if is_final_step: 
            self.microversions_descrip = get_microversions_descrip(user, q_info)
        
        self.save() 


#################### Helper API calls ####################
def get_microversions_descrip(user: AuthUser, q_info: Tuple[str]) -> List[Any]: 
    """ Retrieve all microversions (descriptions and timestamps) of the 
    workspace element as a record of all user actions during the design 
    process. 
    
    q_info: [domain, did, begin_mid, end_mid, eid, etype] at the time of completion 
    """

    def get_doc_history(mid: str): 
        """ Call the getDocumentHistory endpoint to get the last 20 
        microversions of the document, starting from the mid argument. 
        """
        response = requests.get(
            os.path.join(
                q_info[0], # os_domain 
                "api/documents/d/{}/m/{}/documenthistory".format(
                    q_info[1], mid
                )
            ), 
            headers={
                "Content-Type": "application/json", 
                "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
                "Authorization": "Bearer " + user.access_token
            }
        )
        if response.ok: 
            return response.json() 
        else: 
            return None 

    def clean_history(raw_history: List[Dict[str, str]]): 
        """ Given a document history with microversions from the API call, 
        this function cleans the API response to remove personal identifiers. 
        """
        output_history = [] 
        for item in raw_history: 
            item.pop("username") # remove username 
            output_history.append(item)
            # Check if reaching the begining microversion ID 
            if item["microversionId"] == q_info[2]: 
                break 
        return output_history

    # Check if user's OAuth token still valid 
    if user.expires_at <= timezone.now() + timedelta(minutes=10): 
        user.refresh_oauth_token() 
    
    history = [] 
    next_mid = q_info[3] # start from the chronological end 

    while next_mid: 
        temp = get_doc_history(next_mid)
        if temp: 
            temp = clean_history(temp)
        else: 
            break 
        history.extend(temp)
        if temp[-1]['microversionId'] == q_info[2]: 
            break 
        else: 
            next_mid = temp[-1]['nextMicroversionId']
    return history 
        

def get_feature_list(user: AuthUser, q_info: Tuple[str]) -> Any: 
    """ Retrieve the full feature list of the submitted Part Studio with 
    semantic and parametric information of the features. 

    q_info: [domain, did, begin_mid, end_mid, eid, etype] at the time of completion 
    """
    response = requests.get(
        os.path.join(
            q_info[0], 
            "api/{}/d/{}/m/{}/e/{}/features".format(
                q_info[5], q_info[1], q_info[3], q_info[4]
            )
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
            "Authorization": "Bearer " + user.access_token
        }
    )
    if response.ok: 
        return response.json() 
    else: 
        return None 


def get_shaded_view(
    user: AuthUser, q_info: Tuple[str], view_mat: List[float], 
    output_dim=(128, 128), pixel_size=0
) -> str: 
    """ Generate the shaded view of the element as a base64-encoded string of PNG image 
    
    q_info: [domain, did, begin_mid, end_mid, eid, etype] at the time of completion 
    output_dim: Tuple[outputHeight, outputWidth]
    """
    response = requests.get(
        os.path.join(
            q_info[0], 
            "api/{}/d/{}/m/{}/e/{}/shadedviews".format(
                q_info[5], q_info[1], q_info[3], q_info[4]
            )
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
            "Authorization": "Bearer " + user.access_token
        }, 
        params={
            "viewMatrix": str(view_mat)[1:-1], 
            "outputHeight": output_dim[0], 
            "outputWidth": output_dim[1], 
            "pixelSize": pixel_size
        }
    )
    if response.ok: 
        return f"data:image/png;base64,{response.json()['images'][0]}"
    else: 
        return ""


def get_stl_mesh(user: AuthUser, q_info: Tuple[str], rollbackBarIndex=-1) -> str: 
    """ Export the mesh representation of the part studio in STL format (base64 encoded)
    To view the original data in bytes: base64.b64decode(data)

    q_info: [domain, did, begin_mid, end_mid, eid, etype] at the time of completion 
    """
    response = requests.get(
        os.path.join(
            q_info[0], 
            "api/partstudios/d/{}/m/{}/e/{}/gltf".format(
                q_info[1], q_info[3], q_info[4]
            )
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "model/gltf-binary;qs=0.08", 
            "Authorization": "Bearer " + user.access_token
        }, 
        params={
            "rollbackBarIndex": rollbackBarIndex
        }
    )
    if not response.ok: 
        return ""
    # Convert GLB format to STL format for storage 
    mesh = trimesh.load(
        trimesh.util.wrap_as_stream(response.content), 
        file_type="glb", force="mesh"
    )
    stl_mesh = trimesh.exchange.stl.export_stl(mesh)
    return base64.b64encode(stl_mesh).decode()


def get_assembly_definition(user: AuthUser, q_info: Tuple[str], includeMateFeatures=True) -> Any: 
    """ Get the definition of the assembly, including all part instances and mates 

    q_info: [domain, did, begin_mid, end_mid, eid, etype] at the time of completion 
    """
    response = requests.get(
        os.path.join(
            q_info[0], 
            "api/assemblies/d/{}/m/{}/e/{}".format(
                q_info[1], q_info[3], q_info[4]
            )
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
            "Authorization" : "Bearer " + user.access_token
        }, 
        params={
            "includeMateFeatures": includeMateFeatures 
        }
    )
    if response.ok: 
        return response.json() 
    else: 
        return None 
