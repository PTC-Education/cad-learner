"""
Development Guide
Last major structural update: Jan. 27, 2023

The Django model class "Question" is a base parent class of all question types. 
Every question type should inheret the properties and methods of the Question class. 

When creating new question types: 
1.  Add new question type specification in the QuestionType class 
2.  Create a new class for the new question type, which inherets the Question class 
3.  First add additional fields required for the question type on top of all the 
    default fields available in the Question class 
4.  Add the following default methods to the question type class: 
    (i).    publish(self): check if all necessary information is availble to be 
            published 
    (ii).   initiate_actions(self, AuthUser): any actions required to prepare the 
            starting document for the user, e.g., import a starting part 
    (iii).  evaluate(self, AuthUser): when a user submits their model for evaluation, 
            specify the checks required to evaluate correctness 
                - Also initiate data collection after evaluation 
    (iv).   show_result(self, AuthUser): by default, distribution of the time spent 
            to complete the question is shown in the Question class. Additional 
            distributions and/or statistics should be specified in this method 
    (v).    save(self): initial information to be retrieved from Onshape when a 
            question is first added by the admin
5.  Add additional methods if required 
6.  Add the new question type class to the Q_Type_Dict variables in all models.py 
    and views.py files in this project 
7.  Design and create a new HistoryData class model in the data_miner app to 
    collect data for failed and successful submissions 
"""

import io 
import os 
import requests
import base64
from datetime import datetime, timedelta
from typing import Union, Tuple, Any

import numpy as np 
import numpy.typing as npt 
from matplotlib.figure import Figure 
from matplotlib.backends.backend_agg import FigureCanvasAgg

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy 


#################### Create your models here ####################
class QuestionType(models.TextChoices): 
    # Every text choice should have at most 4 letters 
    UNKNOWN = 'UNKN', gettext_lazy('Unknown')
    SINGLE_PART_PS = 'SPPS', gettext_lazy('Single-part Part Studio')
    MULTI_PART_PS = 'MPPS', gettext_lazy('Multi-part Part Studio')


class ElementType(models.TextChoices): 
    # The corresponding values will be used for API calls 
    NA = "N/A", gettext_lazy("Not Applicable")
    PARTSTUDIO = "partstudios", gettext_lazy("Part Studio")
    ASSEMBLY = "assemblies", gettext_lazy("Assembly")
    ALL = "all", gettext_lazy("All Types")


class AuthUser(models.Model): 
    os_user_id = models.CharField(max_length=30, default=None, unique=True)
    
    os_domain = models.URLField(max_length=100, null=True)
    did = models.CharField(max_length=30, null=True)
    wid = models.CharField(max_length=30, null=True)
    eid = models.CharField(max_length=30, null=True)
    etype = models.CharField(max_length=40, choices=ElementType.choices, null=True)

    access_token = models.CharField(max_length=100, null=True)
    refresh_token = models.CharField(max_length=100, null=True)
    expires_at = models.DateTimeField(null=True)

    modelling = models.BooleanField(default=False)
    # The following fields are only applicable when modelling 
    last_start = models.DateTimeField(null=True) 
    curr_question_type = models.CharField(max_length=4, choices=QuestionType.choices, null=True)
    curr_question_id = models.CharField(max_length=400, null=True) 
    start_mid = models.CharField(max_length=30, null=True) 
    end_mid = models.CharField(max_length=30, null=True) 
    add_field = models.JSONField(
        default=dict, null=True, 
        help_text="An additional field that can be used for some question types to store additional data in the user's model"
    )
    
    completed_history = models.JSONField(default=dict)
    """
    completed_history = Dict[
        str(question): List[Tuple[completion_datetime, time_taken, ...]]
    ]

    For SPPS and MPPS: ... includes feature_cnt
    """

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
        self.expires_at = timezone.now() + timedelta(seconds=response['expires_in'])
        self.save() 
        return None 

    def __str__(self) -> str:
        return self.os_user_id


class Question(models.Model): 
    """ This is the base class for all question types. 
    It stores all the common fields required for front end, while 
    question-type specific fields should be added to the specific 
    model class. 
    """
    class DifficultyLevel(models.TextChoices): 
        # Every text choice should have at most 2 letters 
        UNCLASSIFIED = "NA", gettext_lazy("Unclassified")
        CHALLENGING = "CH", gettext_lazy("Challenging") 
        MEDIUM = "ME", gettext_lazy("Medium")
        EASY = "EA", gettext_lazy("Easy")

    # An auto-generated (incremental) id for every question  
    question_id = models.BigAutoField(primary_key=True)
    
    question_type = models.CharField(
        max_length=4, 
        choices=QuestionType.choices, 
        default=QuestionType.UNKNOWN
    )
    difficulty = models.CharField(
        max_length=2, 
        choices=DifficultyLevel.choices, 
        default=DifficultyLevel.UNCLASSIFIED
    )
    allowed_etype = models.CharField(
        "Allowed element type(s)", 
        max_length=40, 
        choices=ElementType.choices, 
        default=ElementType.ALL, 
        help_text="Allowed Onshape element type(s) that can start this question."
    )

    # IDs to be linked 
    did = models.CharField( 
        "Onshape document ID", 
        max_length=40, default=None
    )
    vid = models.CharField(
        "Onshape version ID", 
        max_length=40, default=None
    )
    eid = models.CharField(
        "Onshape element ID", 
        max_length=40, default=None, 
        help_text="The Onshape element ID that the thumbnail image will be taken from. It should capture the expected solution to the question."
    )
    etype = models.CharField(
        "Onshape element type", 
        max_length=40, 
        choices=ElementType.choices, 
        default=ElementType.NA, 
        help_text="The Onshape element type of the element which ID is given for thumbnial image."
    )
    os_drawing_eid = models.CharField(
        "Onshape element ID of the main Onshape drawing", 
        max_length=40, null=True, unique=True, 
        help_text="Element ID of the Onshape drawing that users can open in a new tab."
    ) 
    jpeg_drawing_eid = models.CharField(
        "Onshape element ID of a JPEG export of a drawing", 
        max_length=40, null=True, unique=True, 
        help_text="Export a drawing as a JPEG to the questions document and input that element ID here. Portrait rather than landscape is preferred."
    ) 

    # Question completion stats
    completion_count = models.PositiveIntegerField(
        default=0, help_text="The number of times this question is completed by users"
    )
    completion_time = models.JSONField(
        default=list, help_text="List of completion time (in seconds) by users in history"
    )

    # Admin-specified parameters for the question 
    question_name = models.CharField(
        max_length=400, null=True, unique=True, 
        help_text="A unique name for the question that will be displayed to the users"
    )
    additional_instructions = models.TextField(
        null=True, default=None, blank=True, 
        help_text="(Opitonal) additional instructions for users"
    )

    # Images to be displayed 
    thumbnail = models.TextField(null=True)
    drawing_jpeg = models.TextField(null=True)
    
    # This boolean indicates when the system check is passed 
    published = models.BooleanField(
        default=False, help_text="Users can only access the model after it is published"
    )

    def __str__(self) -> str:
        # Text/String representation of the question 
        return self.question_type + "_" + str(self.question_id)

    def publishable(self) -> bool: 
        if self.question_name and self.os_drawing_eid: 
            return True 
        else: 
            return False 

    def show_result(self, user: AuthUser) -> str: 
        """ By default, the time spent to completion of a question of all users 
        is visualized through a distribution plot, and the relative position of 
        the user is labelled. For every question type, specific additional 
        distributions may also be added in corresponding subclasses. 
        """
        # Print out user's time spent 
        my_time = user.completed_history[str(self)][-1][1] # in seconds
        output = "<p>You completed the model {} in {} minutes and {} seconds.</p>".format(
            self.question_name, int(my_time // 60), int(my_time % 60)
        )

        # Plot a histogram of time spent 
        if len(self.completion_time) >= 10: 
            output += """
            <p>Take a look at how you did compared to other people who also completed this model:</p>
            <img src="{}" alt="stats_time"/>
            """.format(
                plot_dist(
                    np.array(self.completion_time) / 60, 
                    my_time / 60, x_label="Time Spent to Complete This Question (mins)"
                )
            )
        return output 

    def save(self, *args, **kwargs): 
        if not self.thumbnail: 
            self.thumbnail = get_thumbnail(self) 
        if not self.drawing_jpeg: 
            self.drawing_jpeg = get_jpeg_drawing(self)
        return super().save(*args, **kwargs)


class Question_SPPS(Question): 
    # Additional analytics to be collected and presented 
    completion_feature_cnt = models.JSONField(
        default=list, help_text="List of feature counts required by users in history"
    )

    # Properties for evaluation 
    model_mass = models.FloatField(null=True, help_text="Mass in kg")
    model_volume = models.FloatField(null=True, help_text="Volume in m^3")
    model_SA = models.FloatField(null=True, help_text="Surface area in m^2")
    model_inertia = models.JSONField(null=True, help_text="3 element array describing the Principal Interia")

    class Meta: 
        verbose_name = "Single-part Part Studio Question"

    def publish(self) -> None: 
        if self.published: 
            self.published = False 
        else: 
            # Check if necessary information is present
            if self.publishable() and self.model_mass: 
                self.published = True 
        self.save() 
        return None 

    def initiate_actions(self, user: AuthUser) -> bool: 
        """ No initiating actions are required. 
        """
        return True 

    def evaluate(self, user: AuthUser) -> Union[str, bool]: 
        """ Given the user submiting a model for evaluation, this function checks if the 
        user model matches the reference model. 
        - If evaluation passed, True is returned. 
        - If evaluation cannot proceed due to API errors, False is returned. 
        - If evaluation found mismatch, a table showing the difference is returned to 
          be displayed in the HTML page. 
        """
        # Get info from user model 
        feature_list = get_feature_list(user)
        mass_prop = get_mass_properties(
            user.did, "w", user.wid, user.eid, user.etype, massAsGroup=True,
            auth_token="Bearer " + user.access_token
        )
        if not feature_list or not mass_prop: # API call failed 
            return False 

        # Check if there are parts 
        if len(mass_prop['bodies']) == 0: 
            return "No parts found - please model the part then try re-submitting.", False 
        
        # Check if there are derived parts 
        for fea in feature_list['features']: 
            if fea['featureType'] == 'importDerived': 
                return "It is detected that your model contains derived features through import. Please complete the task with native Onshape features only and resubmit for evaluation ...", False 

        # Compare property values 
        ref_model = [self.model_mass, self.model_volume, self.model_SA, self.model_inertia[0]]
        user_model = [
            mass_prop['bodies']['-all-']['mass'][0], 
            mass_prop['bodies']['-all-']['volume'][0], 
            mass_prop['bodies']['-all-']['periphery'][0],
            mass_prop['bodies']['-all-']['principalInertia'][0]
        ]
        check_symbols = [] 
        check_pass = True 
        err_allowance = 0.005 
        for i, item in enumerate(ref_model): 
            # Check for accuracy 
            if (
                item * (1 - err_allowance) > user_model[i] or 
                user_model[i] > item * (1 + err_allowance)
            ): 
                check_pass = False 
                check_symbols.append("&#x2717;")
            else: 
                check_symbols.append("&#x2713;")
            # Round for display 
            if item < 0.1 or item > 99: 
                ref_model[i] = '{:.2e}'.format(ref_model[i])
                user_model[i] = '{:.2e}'.format(user_model[i])
            else: 
                ref_model[i] = round(ref_model[i], 3)
                user_model[i] = round(user_model[i], 3)

        if not check_pass: 
            # Prepare error message 
            fail_msg = '''
            <table>
                <tr>
                    <th>Properties</th>
                    <th>Expected Values</th>
                    <th>Actual Values</th>
                    <th>Check</th>
                </tr>
            '''
            prop_name = ["Mass (kg)", "Volume (m^3)", "Surface Area (m^2)", "Principal Inertia Min (kg.m^2)"]
            for i, item in enumerate(prop_name): 
                fail_msg += f'''
                <tr>
                    <td>{item}</td>
                    <td>{ref_model[i]}</td>
                    <td>{user_model[i]}</td>
                    <td>{check_symbols[i]}</td>
                </tr>
                '''
            # Return failure messages 
            if not user.end_mid: # first failure 
                user.end_mid = get_microversion(user)
                user.save() 
                return fail_msg + "</table>", True 
            else: 
                return fail_msg + "</table>", False
        else: 
            # Initiate data collection from data_miner 
            # Update database to record success 
            time_spent = (timezone.now() - user.last_start).total_seconds()
            feature_cnt = len(feature_list['features'])
            end_mid = get_microversion(user)

            self.completion_count += 1
            self.completion_time.append(time_spent)
            self.completion_feature_cnt.append(feature_cnt)
            self.save()

            user.end_mid = end_mid
            user.modelling = False 
            if str(self) in user.completed_history: 
                user.completed_history[str(self)].append((
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent, feature_cnt
                ))
            else: 
                user.completed_history[str(self)] = [(
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent, feature_cnt
                )]
            user.save() 
            return True 
    
    def show_result(self, user: AuthUser) -> str: 
        """ Other than the default time spent comparison, also plot the 
        distribution of features used to complete the question. 
        """
        my_fea_cnt = user.completed_history[str(self)][-1][2] 
        output = "<p>You completed the model {} with {} features.</p>".format(
            self.question_name, int(my_fea_cnt)
        )
        # Plot a histogram of feature counts 
        if len(self.completion_feature_cnt) >= 10: 
            output += """<img src="{}" alt="stats_time"/>""".format(
                plot_dist(
                    self.completion_feature_cnt, my_fea_cnt, 
                    x_label="Number of Features Used to Complete This Question"
                )
            )
        return super().show_result(user) + output

    def save(self, *args, **kwargs): 
        self.question_type = QuestionType.SINGLE_PART_PS
        self.etype = ElementType.PARTSTUDIO
        if not self.model_mass: 
            mass_prop = get_mass_properties(
                self.did, "v", self.vid, self.eid, self.etype, massAsGroup=True
            )
            if mass_prop: 
                self.model_mass = mass_prop['bodies']['-all-']['mass'][0]
                self.model_volume = mass_prop['bodies']['-all-']['volume'][0]
                self.model_SA = mass_prop['bodies']['-all-']['periphery'][0]
                self.model_inertia = mass_prop['bodies']['-all-']['principalInertia']
            self.save() 
        return super().save(*args, **kwargs)


class Question_MPPS(Question): 
    # Additional question information 
    starting_eid = models.CharField(
        "Starting element ID", 
        max_length=40, default=None, null=True, 
        help_text="(Optional) Starting part studio that need to be imported to user document with derived features. Leave blank if none is required."
    )
    mid = models.CharField(
        max_length=40, default=None, null=True, 
        help_text="Last microversion of the starting element's version"
    )

    # Additional analytics to be collected and presented 
    completion_feature_cnt = models.JSONField(
        default=list, help_text="List of feature counts required by users in history"
    )

    # Properties for evaluation 
    model_mass = models.JSONField(default=list, null=True, help_text="Mass in kg")
    model_volume = models.JSONField(default=list, null=True, help_text="Volume in m^3")
    model_SA = models.JSONField(default=list, null=True, help_text="Surface area in m^2")

    class Meta: 
        verbose_name = "Multi-part Part Studio Question"

    def publish(self) -> None: 
        if self.published: 
            self.published = False 
        else: 
            # Check if necessary information is present 
            if (
                self.publishable() and self.model_mass and 
                (not self.starting_eid or self.mid)
            ): 
                self.published = True 
        self.save() 
        return None 

    def initiate_actions(self, user: AuthUser) -> bool: 
        """ Initiating actions are required to import starting parts to the user's 
        document with derived features when they start the question. 
        Return True if successful, otherwise False 
        """
        # Insert the all starting parts from the starting document to user's working 
        # document as one derived part 
        response = requests.post(
            os.path.join(
                user.os_domain, 
                "api/partstudios/d/{}/w/{}/e/{}/features".format(
                    user.did, user.wid, user.eid
                )
            ), 
            headers={
                "Content-Type": "application/json", 
                "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
                "Authorization" : "Bearer " + user.access_token
            }, 
            json={
                 "feature": {
                    "btType": "BTMFeature-134",
                    "name": "Derived Starting Parts",
                    "parameters": [
                        {
                            "btType": "BTMParameterQueryList-148",
                            "queries": [
                                {
                                    "btType": "BTMIndividualQuery-138",
                                    "queryStatement": None,
                                    "queryString": "query=qEverything(EntityType.BODY);"
                                }
                            ], 
                            "parameterId": "parts"
                        },
                        {
                            "btType": "BTMParameterDerived-864",
                            "parameterId": "buildFunction",
                            "namespace": "d{}::v{}::e{}::m{}".format(
                                self.did, self.vid, self.starting_eid, self.mid
                            ),
                            "imports": []
                        }
                    ],
                    "featureType": "importDerived"
                }
            }
        )
        if not response.ok: 
            return False 
        else: 
            # Store the import derived feature ID for evaluation 
            user.add_field = {
                "MPPS_Derived_ID": response.json()['feature']['featureId']
            }
            user.save()
            return True

    def geo_check(self, user_prop, err_tol=0.005) -> Union[bool, str]: 
        """
        The model is considered to be correct if for every part in the reference model, 
        there is one and only one part in the user's model with matching properties. 
        Limitation: avoid having parts with properties that are too closed numerically. 
        """
        ref_prop = [self.model_mass, self.model_volume, self.model_SA]
        ref_prop = sorted(
            [
                (ref_prop[0][i], ref_prop[1][i], ref_prop[2][i]) 
                for i in range(len(ref_prop[0]))
            ], 
            key=lambda x : x[0]
        )
        user_prop = sorted(
            [
                (user_prop[0][i], user_prop[1][i], user_prop[2][i]) 
                for i in range(len(user_prop[0]))
            ], 
            key=lambda x : x[0]
        )

        eval_result = [] 
        for i, props in enumerate(ref_prop): 
            check_pass = True 
            for j, prop in enumerate(props): 
                if (
                    prop * (1 + err_tol) < user_prop[i][j] or 
                    prop * (1 - err_tol) > user_prop[i][j]
                ): 
                    check_pass = False 
            eval_result.append(check_pass)
        
        if not False in eval_result: 
            return True 
        else: 
            return "You have modelled {} out of {} parts correctly.".format(
                eval_result.count(True), len(eval_result)
            )

    def evaluate(self, user: AuthUser) -> Union[Tuple[Union[str, bool]], bool]: 
        """ Given the user submiting a model for evaluation, this function checks if the 
        user model matches the reference model. 
        - If evaluation passed, True is returned. 
        - If evaluation cannot proceed due to API errors, False is returned. 
        - If evaluation found mismatch, a table showing the difference is returned to 
          be displayed in the HTML page. Returns: Tuple[err_message, ?collect_fail_data]
        """
        # Get info from user model 
        feature_list = get_feature_list(user)
        mass_prop = get_mass_properties(
            user.did, "w", user.wid, user.eid, user.etype, massAsGroup=False, 
            auth_token="Bearer " + user.access_token
        )
        if not feature_list or not mass_prop: # API call failed 
            return False 

        if len(mass_prop['bodies']) == 0: # Check if there are parts 
            return "No parts found - please model the part then try re-submitting.", False 
        elif len(mass_prop['bodies']) != len(self.model_mass): # Check num of parts 
            err_msg = "The number of parts in your Part Studio does not match the reference Part Studio."
            if not user.end_mid: # first failure 
                user.end_mid = get_microversion(user)
                user.save() 
                return err_msg, True 
            else: 
                return err_msg, False 

        # Check if there are derived parts other than those imported for initiation 
        for fea in feature_list['features']: 
            if (
                fea['featureType'] == 'importDerived' and 
                (not self.starting_eid or fea['featureId'] != user.add_field['MPPS_Derived_ID'])
            ): 
                return "It is detected that your model contains derived features through import. Please complete the task with native Onshape features only and resubmit for evaluation ...", False 
        
        # Compare property values 
        eval_correct = self.geo_check(
            [
                [prt['mass'][0] for prt in mass_prop['bodies'].values()], 
                [prt['volume'][0] for prt in mass_prop['bodies'].values()], 
                [prt['periphery'][0] for prt in mass_prop['bodies'].values()]
            ]
        )
        if not type(eval_correct) is bool: 
            if not user.end_mid: # first failure 
                user.end_mid = get_microversion(user)
                user.save() 
                return eval_correct, True 
            else: 
                return eval_correct, False 
        else: 
            # Update database to record success 
            time_spent = (timezone.now() - user.last_start).total_seconds()
            feature_cnt = len(feature_list['features'])
            end_mid = get_microversion(user)

            self.completion_count += 1
            self.completion_time.append(time_spent)
            self.completion_feature_cnt.append(feature_cnt)
            self.save()

            user.end_mid = end_mid
            user.modelling = False 
            if str(self) in user.completed_history: 
                user.completed_history[str(self)].append((
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent, feature_cnt
                ))
            else: 
                user.completed_history[str(self)] = [(
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent, feature_cnt
                )]
            user.save() 
            return True 

    def show_result(self, user: AuthUser) -> str: 
        """ Other than the default time spent comparison, also plot the 
        distribution of features used to complete the question. 
        """
        my_fea_cnt = user.completed_history[str(self)][-1][2] 
        output = "<p>You completed the model {} with {} features.</p>".format(
            self.question_name, int(my_fea_cnt)
        )
        # Plot a histogram of feature counts 
        if len(self.completion_feature_cnt) >= 10: 
            output += """<img src="{}" alt="stats_time"/>""".format(
                plot_dist(
                    self.completion_feature_cnt, my_fea_cnt, 
                    x_label="Number of Features Used to Complete This Question"
                )
            )
        return super().show_result(user) + output

    def save(self, *args, **kwargs): 
        self.question_type = QuestionType.MULTI_PART_PS
        self.etype = ElementType.PARTSTUDIO
        self.allowed_etype = ElementType.PARTSTUDIO
        if self.starting_eid and not self.mid: 
            ele_info = get_elements(self, self.starting_eid)
            if ele_info: 
                self.mid = ele_info[0]['microversionId']
        if not self.model_mass: 
            mass_prop = get_mass_properties(
                self.did, "v", self.vid, self.eid, self.etype, massAsGroup=False 
            )
            if mass_prop: 
                self.model_mass = [
                    part['mass'][0] for part in mass_prop['bodies'].values()
                ]
                self.model_volume = [
                    part['volume'][0] for part in mass_prop['bodies'].values()
                ]
                self.model_SA = [
                    part['periphery'][0] for part in mass_prop['bodies'].values()
                ]
        return super().save(*args, **kwargs)


#################### Helper API calls ####################
_Q_TYPES = Union[Question_SPPS, Question_MPPS] # for function argument hints 
# TODO: better authentication method pending for API calls 
API_KEY = "Basic " + base64.b64encode(
    (os.environ['ADMIN_ACCESS'] + ":" + os.environ['ADMIN_SECRET']).encode()
).decode()


def get_thumbnail(question: _Q_TYPES, auth_token=API_KEY) -> str: 
    """Get a thumbnail image of the question for display 
    """
    response = requests.get(
        "https://cad.onshape.com/api/{}/d/{}/v/{}/e/{}/shadedviews".format(
            question.etype, question.did, question.vid, question.eid
        ), 
        params={
            "outputHeight": 60, 
            "outputWidth": 60, 
            "pixelSize": 0, 
            "viewMatrix": "0.612,0.612,0,0,-0.354,0.354,0.707,0,0.707,-0.707,0.707,0"
        }, 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
            "Authorization": auth_token
        }
    )
    
    if response.ok: 
        return f"data:image/png;base64,{response.json()['images'][0]}"
    else: 
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABmJLR0QA/wD/AP+gvaeTAAAAy0lEQVRIie2VXQ6CMBCEP7yDXkEjeA/x/icQgrQcAh9czKZ0qQgPRp1kk4ZZZvYnFPhjJi5ABfRvRgWUUwZLxIe4asEsMOhndmzhqbtZSdDExxh0EhacRBIt46V5oJDwEd4BuYQjscc90ATiJ8UfgFvEXPNNqotCKtEvF8HZS87wLAeOijeRTwhahsNoWmVi4pWRhLweqe4qCp1kLVUv3UX4VgtaX7IXbmsU0knuzuCz0SEwWIovvirqFTSrKbLkcZ8v+RecVyjyl3AHdAl3ObMLisAAAAAASUVORK5CYII="


def get_jpeg_drawing(question: _Q_TYPES, auth_token=API_KEY) -> str: 
    """ Get the JPEG version of the drawing to be displayed when modelling 
    """
    response = requests.get(
        "https://cad.onshape.com/api/blobelements/d/{}/v/{}/e/{}".format(
            question.did, question.vid, question.jpeg_drawing_eid
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/octet-stream;charset=UTF-8;qs=0.09", 
            "Authorization" : auth_token
        }
    )
    
    if response.ok: 
        response = base64.b64encode(response.content)
        return f"data:image/jpeg;base64,{response.decode('ascii')}"
    else: 
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABmJLR0QA/wD/AP+gvaeTAAAAy0lEQVRIie2VXQ6CMBCEP7yDXkEjeA/x/icQgrQcAh9czKZ0qQgPRp1kk4ZZZvYnFPhjJi5ABfRvRgWUUwZLxIe4asEsMOhndmzhqbtZSdDExxh0EhacRBIt46V5oJDwEd4BuYQjscc90ATiJ8UfgFvEXPNNqotCKtEvF8HZS87wLAeOijeRTwhahsNoWmVi4pWRhLweqe4qCp1kLVUv3UX4VgtaX7IXbmsU0knuzuCz0SEwWIovvirqFTSrKbLkcZ8v+RecVyjyl3AHdAl3ObMLisAAAAAASUVORK5CYII="


def get_mass_properties(
    did: str, wvm: str, wvmid: str, eid: str, etype: str, massAsGroup=True, auth_token=API_KEY
) -> Any: 
    """ Get the mass and geometry properties of the given element 
    """
    response = requests.get(
        "https://cad.onshape.com/api/{}/d/{}/{}/{}/e/{}/massproperties".format(
            etype, did, wvm, wvmid, eid
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
            "Authorization" : auth_token
        }, 
        params={
            "massAsGroup": massAsGroup
        }
    )
    if response.ok: 
        return response.json() 
    else: 
        return None 


def get_feature_list(user: AuthUser) -> Any: 
    """ Retrieve the feature list in the given element 
    """
    response = requests.get(
        os.path.join(
            user.os_domain, 
            "api/{}/d/{}/w/{}/e/{}/features".format(
                user.etype, user.did, user.wid, user.eid
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


def get_microversion(user: AuthUser) -> Union[str, None]: 
    """ Get the current microversion of the user's working document 
    """
    response = requests.get(
        os.path.join(
            user.os_domain, 
            "api/documents/d/{}/w/{}/currentmicroversion".format(
                user.did, user.wid
            )
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
            "Authorization": "Bearer " + user.access_token
        }
    )
    if response.ok: 
        return response.json()['microversion']
    else: 
        return None 


def get_elements(question: _Q_TYPES, elementId=None, auth_token=API_KEY) -> Any: 
    """ Get all elements in a document's version and their information 
    """
    response = requests.get(
        "https://cad.onshape.com/api/documents/d/{}/v/{}/elements".format(
            question.did, question.vid
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
            "Authorization" : auth_token
        }, 
        params={
            "elementId": elementId
        }
    )
    if response.ok: 
        return response.json() 
    else: 
        return None 


#################### Other helper functions ####################
def plot_dist(
    dist_data: npt.ArrayLike, label_val: Union[float, bool], label_avg=True, 
    x_label="", y_label="Number of Users"
) -> str: 
    """ Ploot distribution of the given data and label relative position 
    of the user in the distribution. 
    """
    # Plot 
    fig = Figure() 
    ax = fig.add_subplot(1, 1, 1)
    ax.hist(dist_data)
    if label_avg: 
        ax.axvline(
            np.mean(dist_data), ls='--', c='k', label="Average"
        )
        ax.legend() 
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    # Label my position in the distribution
    if label_val: 
        patches = ax.patches
        for patch in list(reversed(patches)): 
            if (
                round(patch.get_x(), 2) <= label_val and 
                round(patch.get_x() + patch.get_width(), 2) >= label_val
            ): 
                # Mark where the user is at
                ax.text(
                    patch.get_x() + patch.get_width() / 2, 
                    patch.get_height() + 0.1, 
                    "Me", ha="center", va="bottom"
                )
                break 
    # Data conversion 
    img_output = io.BytesIO() 
    FigureCanvasAgg(fig).print_png(img_output)
    img_output.seek(0)
    img_data = base64.b64encode(img_output.read())
    return "data:image/png;base64," + str(img_data)[2:-1]
