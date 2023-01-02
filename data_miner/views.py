import datetime
import requests 
from typing import List, Dict

from rq import Queue 
from worker import conn

from django.shortcuts import get_object_or_404
from django.http import HttpRequest
from django.utils import timezone

from questioner.models import AuthUser, Question
from .models import HistoryData


# The RQ queue that processes all time-consuming data mining operations 
# in the background 
q = Queue(connection=conn)

# Create your views here.
def get_process_data(data_entry: HistoryData, user: AuthUser, q_info: List[str]): 
    """ Retrieve all microversions (descriptions and timestamps) of the 
    workspace element as a record of all user actions during the design 
    process. 

    Args: 
        - data_entry: the HistoryData model entry that data to be saved in 
        - user: an AuthUser model (with OAuth tokens)
        - q_info: the task completion information 
                  [domain, did, begin_mid, end_mid, eid]
    """

    def get_doc_history(mid: str): 
        """ Call the getDocumentHistory endpoint to get the last 20 
        microversions of the document, starting from the mid argument. 
        """
        response = requests.get(
            "{}/api/documents/d/{}/m/{}/documenthistory".format(
                q_info[0], q_info[1], mid
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
        this function cleans the API response to remove personal 
        identifiers. 
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
    if user.expires_at <= timezone.now() + datetime.timedelta(minutes=10): 
        user.refresh_oauth_token() 
    
    history = [] 
    next_mid = q_info[3] # start from the chronological end 

    while next_mid: 
        temp = get_doc_history(next_mid)
        if temp: 
            temp = clean_history(temp)
        else: 
            return history 
        history.extend(temp)
        if temp[-1]['microversionId'] == q_info[2]: 
            next_mid = None 
            break 
        else: 
            next_mid = temp[-1]['nextMicroversionId']

    data_entry.microversions = history 
    data_entry.save() 
    return None


def get_product_data(data_entry: HistoryData, user: AuthUser, q_info: List[str]): 
    """ Retrieve the following information about the design product 
    to allow pseudo-reconstruction of the model geometrically: 
        1. PS feature list: semantic and geometric definitions of 
                all features
        2. PS FeatureScript definition: Onshape-specific FeatureScript
                definition of the Part Studio 
        3. Mesh model (in glTF format) of the part after every 
                non-sketch and non-plane feature in the construction 
                process 
        4. Two shaded view screenshots (128 x 128 PNG) of the part 
                after every 3D feature (see point above)

    Args: 
        - data_entry: the HistoryData model entry that data to be saved in 
        - user: an AuthUser model (with OAuth tokens)
        - q_info: the task completion information 
                  [domain, did, begin_mid, end_mid, eid]
    """
    
    def get_feature_list(): 
        """ Retrieve the full feature list of the submitted Part Studio with 
        semantic and parametric information of the features. 
        """
        response = requests.get(
            "{}/api/partstudios/d/{}/m/{}/e/{}/features".format(
                q_info[0], q_info[1], q_info[3], q_info[4]
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
    
    def get_fs_def(): 
        """ Retrieve the full Onshape FeatureScript definition of the
        Part Studio. 
        """
        response = requests.get(
            "{}/api/partstudios/d/{}/m/{}/e/{}/featurescriptrepresentation".format(
                q_info[0], q_info[1], q_info[3], q_info[4]
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

    def get_mesh(_rollback_ind: List[int]): 
        """ Get glTF representation of the model's mesh after every non-sketch 
        and non-plane feature in the final submitted model. 

        Args: 
            - _rollback_ind: all indices the rollback bar needs to be moved to 

        Returns: 
            List[Dict[
                "rollbackBarIndex": int, 
                "mesh": gltf-json
            ]]
            All mesh data are stored in glTF-JSON format in bytes 
        """
        result = []
        for ind in _rollback_ind: 
            temp = {"rollbackBarIndex": ind}
            response = requests.get(
                "{}/api/partstudios/d/{}/m/{}/e/{}/gltf".format(
                    q_info[0], q_info[1], q_info[3], q_info[4]
                ), 
                headers={
                    "Content-Type": "application/json", 
                    "Accept": "model/gltf+json;qs=0.08", 
                    "Authorization": "Bearer " + user.access_token
                }, 
                params={
                    "rollbackBarIndex": ind, # doesn't work now 
                    "precomputedLevelOfDetail": "Medium"
                }
            )
            if response.ok: 
                temp["mesh"] = response.content
            else: 
                temp["mesh"] = ""
            result.append(temp)
        return result 

    def get_image(_rollback_ind: List[int]): 
        """ Get two isometric shaded view images of the model after every non-sketch 
        and non-plane feature in the final submitted model. Image 1 captures front, 
        top, right faces, and image 2 captures back, bottom, left faces. 
        
        Args: 
            - _rollback_ind: all indices the rollback bar needs to be moved to 

        Returns: 
            List[Dict[
                "rollbackBarIndex": int, 
                "view1": str, 
                "view2": str
            ]]
            All views are base64 encoded PNG images of size 128 x 128 pixels 
        """
        
        def shaded_view_api(roll_ind: int, view_mat: List[float]): 
            """ Make API call to get shaded view with specified 
            rollback bar index and view matrix. 
            """
            response = requests.get(
                "{}/api/partstudios/d/{}/m/{}/e/{}/shadedviews".format(
                    q_info[0], q_info[1], q_info[3], q_info[4]
                ), 
                headers={
                    "Content-Type": "application/json", 
                    "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
                    "Authorization": "Bearer " + user.access_token
                }, 
                params={
                    "viewMatrix": str(view_mat)[1:-1], 
                    "outputHeight": 128, 
                    "outputWidth": 128, 
                    "pixelSize": 0, 
                    "rollbackBarIndex": roll_ind # to be added 
                }
            )
            if response.ok: 
                return "data:image/png;base64," + response.json()['images'][0]
            else: 
                return ""

        view_mat_1 = [
            0.707, 0.707, 0., 0., 
            -0.408, 0.408, 0.816, 0., 
            0.577, -0.577, 0.577, 0.
        ] # captures front, top, right faces 
        view_mat_2 = [
            -0.707, -0.707, 0., 0., 
            -0.408, 0.408, 0.816, 0., 
            -0.577, 0.577, -0.577, 0.
        ] # captures back, bottom, left faces 
        
        result = [] 
        for ind in rollback_ind: 
            temp = {"rollbackBarIndex": ind} 
            temp['view1'] = shaded_view_api(ind, view_mat_1)
            temp['view2'] = shaded_view_api(ind, view_mat_2)
            result.append(temp)
        return result

    # Check if user's OAuth token still valid 
    if user.expires_at <= timezone.now() + datetime.timedelta(minutes=20): 
        user.refresh_oauth_token() 

    data_entry.feature_list = get_feature_list()
    data_entry.fs_representation = get_fs_def() 
    data_entry.save() 

    if data_entry.feature_list: 
        # Get all rollback bar indices after every non-sketch and non-plane features 
        rollback_ind = [] 
        for i, fea in enumerate(data_entry.feature_list): 
            if fea['featureType'] != "newSketch" and fea['featureType'] != "cPlane": 
                rollback_ind.append(i+1)
        # Get product data after each rollbackBarIndex found above 
        data_entry.mesh_data = get_mesh(rollback_ind) 
        data_entry.save() 
        data_entry.shaded_views = get_image(rollback_ind)
        data_entry.save() 
    return None 


def collect_data(request: HttpRequest, os_user_id: str): 
    """ Once a user submits the model and passes the evaluation check, 
    data of the design process and the product will be collected. This 
    function initiates the collection process. 
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    curr_que = Question.objects.get(question_id=curr_user.curr_question)
    
    completion_data = curr_user.completed_history[curr_que.question_id][-1]

    data_entry = HistoryData(
        os_user_id=os_user_id, 
        question_name=curr_que.question_name, 
        completion_time=datetime.datetime.fromisoformat(completion_data[0]), 
        time_spent=completion_data[1], 
        num_attempt=len(curr_user.completed_history[curr_que.question_id])
    )
    data_entry.save() 
    
    # [domain, did, begin_mid, end_mid, eid]
    query_info = [
        curr_user.os_domain, curr_user.did, curr_user.start_microversion_id, 
        curr_user.end_microversion_id, curr_user.eid
    ]

    # Send the following two time-consuming jobs to the RQ queue 
    q.enqueue(get_process_data, args=[data_entry, curr_user, query_info])
    q.enqueue(get_product_data, args=[data_entry, curr_user, query_info])
    
    return None 