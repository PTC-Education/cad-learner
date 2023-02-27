"""
Development Guide
Last major structural update: Feb. 7, 2023

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
    (iv).   give_up(self, AuthUser): after at least one failed attempt, the user is 
            given the option to give up, and some forms of solutions will be provided
            to the user along with instructions, depending on the question type
    (v).    show_result(self, AuthUser): by default, distribution of the time spent 
            to complete the question is shown in the Question class. Additional 
            distributions and/or statistics should be specified in this method 
    (vi).   save(self): initial information to be retrieved from Onshape when a 
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
from typing import Optional, Iterable, Union, Tuple, Dict, Any

import numpy as np 
import numpy.typing as npt 
from matplotlib.figure import Figure 
from matplotlib.backends.backend_agg import FigureCanvasAgg

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy 
from django.core.exceptions import ObjectDoesNotExist, ValidationError


#################### Create your models here ####################
class QuestionType(models.TextChoices): 
    # Every text choice should have at most 4 letters 
    UNKNOWN = 'UNKN', gettext_lazy('Unknown')
    SINGLE_PART_PS = 'SPPS', gettext_lazy('Single-part Part Studio')
    MULTI_PART_PS = 'MPPS', gettext_lazy('Multi-part Part Studio')
    ASSEMBLY = 'ASMB', gettext_lazy('Assembly Mating')
    MULTI_STEP_PS = 'MSPS', gettext_lazy('Multi-step Part Studio')


class ElementType(models.TextChoices): 
    # The corresponding values will be used for API calls 
    NA = "N/A", gettext_lazy("Not Applicable")
    PARTSTUDIO = "partstudios", gettext_lazy("Part Studio")
    ASSEMBLY = "assemblies", gettext_lazy("Assembly")
    ALL = "all", gettext_lazy("All Types")


class AuthUser(models.Model): 
    os_user_id = models.CharField(max_length=30, default=None, unique=True)
    is_reviewer = models.BooleanField(default=False)
    
    os_domain = models.URLField(max_length=100, null=True)
    did = models.CharField(max_length=30, null=True)
    wid = models.CharField(max_length=30, null=True)
    eid = models.CharField(max_length=30, null=True)
    etype = models.CharField(max_length=40, choices=ElementType.choices, null=True)

    access_token = models.CharField(max_length=100, null=True)
    refresh_token = models.CharField(max_length=100, null=True)
    expires_at = models.DateTimeField(null=True)

    is_modelling = models.BooleanField(default=False)
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
    failure_history = models.JSONField(default=dict)
    """
    history_data = Dict[
        str(question): List[Tuple[completion_datetime, time_taken, ...]]
    ]

    For SPPS, MPPS, and ASMB: ... includes feature_cnt
    For MSPS: ... includes feature_cnt
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


class Reviewer(models.Model): 
    """ A reviewer has the access to view unpublished questions, 
    such that they can try out and review the question. 
    """
    os_user_id = models.CharField(max_length=30, default=None, unique=True)
    user_name = models.CharField(max_length=500, default=None, unique=True)
    is_main_admin = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.user_name

    def save(self, *args, **kwargs): 
        try: 
            user = AuthUser.objects.get(os_user_id=self.os_user_id)
            user.is_reviewer = True
            user.save() 
        except ObjectDoesNotExist: 
            raise ValidationError("Reviewers need to first subscribe and open the app once before they can be added ...")
        
        if not self.user_name: 
            if user.expires_at < timezone.now() + timedelta(minutes=10): 
                user.refresh_oauth_token() 
            
            response = requests.get(
                "https://cad.onshape.com/api/users/sessioninfo", 
                headers={
                    "Content-Type": "application/json", 
                    "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
                    "Authorization" : "Bearer " + user.access_token
                }
            )
            if response.ok: 
                response = response.json() 
                self.user_name = response['name']
        return super().save(*args, **kwargs)
    
    def delete(self, using: Any = ..., keep_parents: bool = ...) -> Tuple[int, Dict[str, int]]:
        user = AuthUser.objects.get(os_user_id=self.os_user_id)
        user.is_reviewer = False 
        user.save() 
        return super().delete(using, keep_parents)


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
    is_multi_step = models.BooleanField(
        default=False, help_text="Has multiple steps required for evaluation"
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
    reviewer_completion_count = models.PositiveIntegerField(
        default=0, help_text="The number of times this question is completed by reviewers"
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
    is_published = models.BooleanField(
        default=False, help_text="Users can only access the model after it is published"
    )
    # This boolean indicates if design data should be collected for this quesiton
    is_collecting_data = models.BooleanField(
        default=True, help_text="User design data is only collected when this is set to be True"
    )

    def __str__(self) -> str:
        # Text/String representation of the question 
        return self.question_type + "_" + str(self.question_id)

    def get_avg_time(self) -> str: 
        # Get average completion time required for the question 
        if self.completion_count > 0: 
            avg_time = np.mean(self.completion_time)
            return "{} minutes {} seconds".format(
                int(avg_time // 60), round(divmod(avg_time, 60)[1])
            )
        else: 
            return ""

    def publishable(self) -> bool: 
        if self.question_name and self.os_drawing_eid: 
            return True 
        else: 
            return False 

    def publish(self) -> None: 
        """ Check if all necessary information is available to be published 
        """
        if self.is_published: 
            self.is_published = False 
        else: 
            if self.publishable(): 
                self.is_published = True 
        self.save()
        return None 

    def initiate_actions(self, user: AuthUser) -> bool: 
        """ Any actions required to prepare the starting document for the user 
        E.g., import a starting part 
        """
        return False 
    
    def evaluate(self, user: AuthUser) -> Union[Tuple[str, bool], bool]: 
        """ When a user submits their model for evaluation, specify the checks 
        required to evaluate correctness 
        - If evaluation passed, True is returned. 
        - If evaluation cannot proceed due to API errors, False is returned. 
        - If evaluation found mismatch, a table showing the difference is returned to 
          be displayed in the HTML page. Returns: Tuple[err_message, ?collect_fail_data]
        """
        return False 

    def give_up(self, user: AuthUser) -> Tuple[str, bool]: 
        """ After at least one failed attempt, the user is given the option to 
        give up, and some forms of solutions will be provided to the user along 
        with instructions, depending on the question type
        Returns: Tuple[message, ?collect_data]
        """
        return "<p>Your attempt is now terminated.</p>", False 

    def show_result(self, user: AuthUser, show_best=False) -> str: 
        """ By default, the time spent to completion of a question of all users 
        is visualized through a distribution plot, and the relative position of 
        the user is labelled. For every question type, specific additional 
        distributions may also be added in corresponding subclasses. 
        """
        # Print out user's time spent 
        if show_best: 
            my_time = sorted(user.completed_history[str(self)], key=lambda x:x[1])[0][1] 
        else: 
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
            self.thumbnail = get_thumbnail(self, get_admin_token()) 
        if not self.drawing_jpeg: 
            self.drawing_jpeg = get_jpeg_drawing(self, get_admin_token())
        return super().save(*args, **kwargs)


class Question_SPPS(Question): 
    # Additional analytics to be collected and presented 
    completion_feature_cnt = models.JSONField(
        default=list, help_text="List of feature counts required by users in history"
    )
    ref_mid = models.CharField(
        max_length=40, default=None, null=True, 
        help_text="Last microversion of the reference element's version"
    )

    # Properties for evaluation 
    model_mass = models.FloatField(null=True, help_text="Mass in kg")
    model_volume = models.FloatField(null=True, help_text="Volume in m^3")
    model_SA = models.FloatField(null=True, help_text="Surface area in m^2")
    model_inertia = models.JSONField(default=list, null=True, help_text="3 element array describing the Principal Interia")

    class Meta: 
        verbose_name = "Single-part Part Studio Question"

    def publish(self) -> None: 
        if self.is_published: 
            self.is_published = False 
        else: 
            # Check if necessary information is present
            if self.publishable() and self.model_mass: 
                self.is_published = True 
        self.save() 
        return None 

    def initiate_actions(self, user: AuthUser) -> bool: 
        """ No initiating actions are required. 
        """
        return True 

    def evaluate(self, user: AuthUser) -> Union[Tuple[str, bool], bool]: 
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
            user.did, "w", user.wid, user.eid, user.etype, massAsGroup=True,
            auth_token=user.access_token
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

        # Check if mass is given 
        if not mass_prop['bodies']['-all-']['hasMass']: 
            return "Please remember to assign a material to your part.", False

        # Compare property values 
        eval_correct = single_part_geo_check( 
            self, 
            [
                mass_prop['bodies']['-all-']['mass'][0], 
                mass_prop['bodies']['-all-']['volume'][0], 
                mass_prop['bodies']['-all-']['periphery'][0],
                mass_prop['bodies']['-all-']['principalInertia'][0]
            ]
        )
        if not type(eval_correct) is bool: 
            # Return failure messages 
            if not user.end_mid: # first failure 
                user.end_mid = get_current_microversion(user)
                user.save() 
                return eval_correct, True 
            else: 
                return eval_correct, False
        else: 
            # Update database to record success 
            time_spent = (timezone.now() - user.last_start).total_seconds()
            feature_cnt = len(feature_list['features'])
            end_mid = get_current_microversion(user)

            self.completion_count += 1
            self.completion_time.append(time_spent)
            self.completion_feature_cnt.append(feature_cnt)
            if user.is_reviewer: 
                self.reviewer_completion_count += 1
            self.save()

            user.end_mid = end_mid
            user.is_modelling = False 
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

    def give_up(self, user:AuthUser) -> Tuple[str, bool]: 
        """ If a user gives up on the problem and wants to see the solution, 
        a derived version of the reference part is first inserted into the 
        user's model, and a GIF instruction will be shown to teach the user 
        how to transform the imported part to see mismatch of their model. 
        Returns: Tuple[message, ?collect_data]
        """
        temp_mid = get_current_microversion(user) 
        response = insert_ps_to_ps(
            user, self.did, self.vid, self.eid, self.ref_mid, 
            "Derived Reference Part"
        )
        # Prepare instructions of using the solution 
        if not response: # insert derive fail 
            msg = '''
            <p>To view the solution, please visit the source document to view the reference part.</p>
            <p>Optional: you can also import the reference part(s) into your working Part Studio using the derived feature. Following instructions below, you can line up the reference parts to your own and visualize the difference.</p>
            '''
        else: 
            msg = "<p>The reference parts are imported into your working Part Studio. You can follow instructions below to line up the reference parts to your own and visualize the difference.</p>"
        
        # Determine if data miner should collect data 
        if user.end_mid: # if at least one meaningful attempt evaluated before 
            time_spent = (timezone.now() - user.last_start).total_seconds()
            if str(self) in user.failure_history: 
                user.failure_history[str(self)].append((
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent
                ))
            else: 
                user.failure_history[str(self)] = [(
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent
                )]
            user.end_mid = temp_mid
            user.save() 
            return msg, True 
        else: 
            return msg, False 

    
    def show_result(self, user: AuthUser, show_best=False) -> str: 
        """ Other than the default time spent comparison, also plot the 
        distribution of features used to complete the question. 
        """
        if show_best: 
            my_fea_cnt = sorted(user.completed_history[str(self)], key=lambda x:x[1])[0][2] 
        else: 
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
        return super().show_result(user, show_best=show_best) + output

    def save(self, *args, **kwargs): 
        self.question_type = QuestionType.SINGLE_PART_PS
        self.etype = ElementType.PARTSTUDIO
        self.allowed_etype = ElementType.PARTSTUDIO
        self.is_multi_step = False 
        # Get microversion IDs 
        if not self.ref_mid: 
            ele_info = get_elements(self, auth_token=get_admin_token(), elementId=self.eid)
            if ele_info: 
                self.ref_mid = ele_info[0]['microversionId']
        # Get reference geometries 
        if not self.model_mass: 
            mass_prop = get_mass_properties(
                self.did, "v", self.vid, self.eid, self.etype, 
                auth_token=get_admin_token(), massAsGroup=True
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
    init_mid = models.CharField(
        max_length=40, default=None, null=True, 
        help_text="Last microversion of the starting element's version"
    )
    ref_mid = models.CharField(
        max_length=40, default=None, null=True, 
        help_text="Last microversion of the reference element's version"
    )

    # Additional analytics to be collected and presented 
    completion_feature_cnt = models.JSONField(
        default=list, help_text="List of feature counts required by users in history"
    )

    # Properties for evaluation 
    model_mass = models.JSONField(default=list, null=True, help_text="Mass in kg")
    model_volume = models.JSONField(default=list, null=True, help_text="Volume in m^3")
    model_SA = models.JSONField(default=list, null=True, help_text="Surface area in m^2")
    model_inertia = models.JSONField(default=list, null=True, help_text="List of 3 element array describing the Principal Interia") # list of list of inertia of parts 

    class Meta: 
        verbose_name = "Multi-part Part Studio Question"

    def publish(self) -> None: 
        if self.is_published: 
            self.is_published = False 
        else: 
            # Check if necessary information is present 
            if (
                self.publishable() and self.model_mass and 
                (not self.starting_eid or self.mid)
            ): 
                self.is_published = True 
        self.save() 
        return None 

    def initiate_actions(self, user: AuthUser) -> bool: 
        """ Initiating actions are required to import starting parts to the user's 
        document with derived features when they start the question. 
        Return True if successful, otherwise False 
        """
        if not self.starting_eid: # no initial import required 
            return True 
        # Insert the all starting parts from the starting document to user's working 
        # document as one derived part 
        response = insert_ps_to_ps(
            user, self.did, self.vid, self.starting_eid, self.init_mid, 
            "Derived Starting Parts"
        )
        if not response: 
            return False 
        else: 
            # Store the import derived feature ID for evaluation 
            user.add_field = {"Cached_Derived_ID": response}
            user.save()
            return True

    def evaluate(self, user: AuthUser) -> Union[Tuple[str, bool], bool]: 
        """ Given the user submiting a model for evaluation, this function checks if the 
        user model matches the reference model. 
        - If evaluation passed, True is returned. 
        - If evaluation cannot proceed due to API errors, False is returned. 
        - If evaluation found mismatch, error message is returned to 
          be displayed in the HTML page. Returns: Tuple[err_message, ?collect_fail_data]
        """
        # Get info from user model 
        feature_list = get_feature_list(user)
        mass_prop = get_mass_properties(
            user.did, "w", user.wid, user.eid, user.etype, massAsGroup=False, 
            auth_token=user.access_token
        )
        if not feature_list or not mass_prop: # API call failed 
            return False 

        if len(mass_prop['bodies']) == 0: # Check if there are parts 
            return "No parts found - please model the part then try re-submitting.", False 
        elif len(mass_prop['bodies']) != len(self.model_mass): # Check num of parts 
            err_msg = "The number of parts in your Part Studio does not match the reference Part Studio."
            if not user.end_mid: # first failure 
                user.end_mid = get_current_microversion(user)
                user.save() 
                return err_msg, True 
            else: 
                return err_msg, False 

        # Check if there are derived parts other than those imported for initiation 
        for fea in feature_list['features']: 
            if (
                fea['featureType'] == 'importDerived' and 
                (not self.starting_eid or fea['featureId'] != user.add_field['Cached_Derived_ID'])
            ): 
                return "It is detected that your model contains derived features through import. Please complete the task with native Onshape features only and resubmit for evaluation ...", False 
        
        # Compare property values 
        eval_correct = multi_part_geo_check(
            self, 
            [
                [prt['mass'][0] for prt in mass_prop['bodies'].values()], 
                [prt['volume'][0] for prt in mass_prop['bodies'].values()], 
                [prt['periphery'][0] for prt in mass_prop['bodies'].values()], 
                [prt['principalInertia'][0] for prt in mass_prop['bodies'].values()]
            ]
        )
        if not type(eval_correct) is bool: 
            if not user.end_mid: # first failure 
                user.end_mid = get_current_microversion(user)
                user.save() 
                return eval_correct, True 
            else: 
                return eval_correct, False 
        else: 
            # Update database to record success 
            time_spent = (timezone.now() - user.last_start).total_seconds()
            feature_cnt = len(feature_list['features'])
            end_mid = get_current_microversion(user)

            self.completion_count += 1
            self.completion_time.append(time_spent)
            self.completion_feature_cnt.append(feature_cnt)
            if user.is_reviewer: 
                self.reviewer_completion_count += 1
            self.save()

            user.end_mid = end_mid
            user.is_modelling = False 
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

    def give_up(self, user: AuthUser) -> Tuple[str, bool]: 
        """ After at least one failed attempt, the user is given the option to 
        give up, and the reference parts will be derived imported to the user's 
        working document along with instructions. 
        Returns: Tuple[message, ?collect_data]
        """
        temp_mid = get_current_microversion(user)
        response = insert_ps_to_ps(
            user, self.did, self.vid, self.eid, self.ref_mid, 
            "Derived Reference Parts"
        )
        # Prepare instructions of using the solution 
        if not response: # insert derive fail 
            msg = '''
            <p>To view the solution, please visit the source document to view the reference part.</p>
            <p>Optional: you can also import the reference part(s) into your working Part Studio using the derived feature. Following instructions below, you can line up the reference parts to your own and visualize the difference.</p>
            '''
        else: 
            msg = "<p>The reference parts are imported into your working Part Studio. You can follow instructions below to line up the reference parts to your own and visualize the difference.</p>"
        
        # Determine if data miner should collect data 
        if user.end_mid: # if at least one meaningful attempt evaluated before 
            time_spent = (timezone.now() - user.last_start).total_seconds()
            if str(self) in user.failure_history: 
                user.failure_history[str(self)].append((
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent
                ))
            else: 
                user.failure_history[str(self)] = [(
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent
                )]
            user.end_mid = temp_mid
            user.save() 
            return msg, True 
        else: 
            return msg, False 

    def show_result(self, user: AuthUser, show_best=False) -> str: 
        """ Other than the default time spent comparison, also plot the 
        distribution of features used to complete the question. 
        """
        if show_best: 
            my_fea_cnt = sorted(user.completed_history[str(self)], key=lambda x:x[1])[0][2] 
        else: 
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
        return super().show_result(user, show_best=show_best) + output

    def save(self, *args, **kwargs): 
        self.question_type = QuestionType.MULTI_PART_PS
        self.etype = ElementType.PARTSTUDIO
        self.allowed_etype = ElementType.PARTSTUDIO
        self.is_multi_step = False 
        # Get microversion IDs 
        if not self.ref_mid or (self.starting_eid and not self.init_mid): 
            ele_info = get_elements(self, auth_token=get_admin_token())
            for item in ele_info: 
                if item['id'] == self.eid: 
                    self.ref_mid = item['microversionId']
                elif self.starting_eid and item['id'] == self.starting_eid: 
                    self.init_mid = item['microversionId']
        # Get reference geometries 
        if not self.model_mass: 
            mass_prop = get_mass_properties(
                self.did, "v", self.vid, self.eid, self.etype, 
                auth_token=get_admin_token(), massAsGroup=False 
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
                self.model_inertia = [
                    part['principalInertia'] for part in mass_prop['bodies'].values() 
                ]
        return super().save(*args, **kwargs)


class Question_ASMB(Question): 
    # Additional question information 
    starting_eid = models.CharField(
        "Source Part Studio element ID", 
        max_length=40, default=None, null=True, 
        help_text="Starting part studio with parts that need to be imported to user assembly to be assembled."
    )

    # Additional analytics to be collected and presented 
    completion_feature_cnt = models.JSONField(
        default=list, help_text="List of mate feature counts required by users in history"
    )

    # Properties for evaluation 
    model_inertia = models.JSONField(default=list, null=True, help_text="3 element array describing the Principal Interia")

    class Meta: 
        verbose_name = "Assembly Mating Question"

    def publish(self) -> None: 
        if self.is_published: 
            self.is_published = False 
        else: 
            # Check if necessary information is present
            if self.publishable() and self.model_inertia and self.starting_eid: 
                self.is_published = True 
        self.save() 
        return None 

    def initiate_actions(self, user: AuthUser) -> bool: 
        """ Initiating actions are required to insert parts from the starting 
        Part Studio into users' working assembly as starting parts to be assembled. 
        Return True if successful, otherwise False 
        """
        return create_assembly_instance(
            user, self.did, self.vid, self.starting_eid
        )
        

    def evaluate(self, user: AuthUser) -> Union[Tuple[str, bool], bool]: 
        """ Given the user submiting a model for evaluation, this function checks if the 
        user model matches the reference model. 
        - If evaluation passed, True is returned. 
        - If evaluation cannot proceed due to API errors, False is returned. 
        - If evaluation found mismatch, a table showing the difference is returned to 
          be displayed in the HTML page. Returns: Tuple[err_message, ?collect_fail_data]
        """
        # Get info from user model 
        assembly_def = get_assembly_definition(user)
        mass_prop = get_mass_properties(
            user.did, "w", user.wid, user.eid, user.etype, 
            auth_token=user.access_token
        )
        if not assembly_def or not mass_prop: # API call failed 
            return False 

        # Count number of mates used 
        feature_cnt = len(assembly_def['rootAssembly']['features'])
        for sub_ass in assembly_def['subAssemblies']: 
            feature_cnt += len(sub_ass['features'])
        if feature_cnt == 0: 
            return "No mate features found - please mate the parts then try re-submitting.", False 

        # Compare property values 
        ref_model = self.model_inertia
        user_model = mass_prop['principalInertia']
        err_allowance = 1e-8

        if abs(ref_model[0] - user_model[0]) > ref_model[0] * err_allowance: 
            # Did not pass and return failure messages 
            fail_msg = "<p>The difference between your mated assembly and the reference assembly is larger than the allowed range of tolerance. Please try again and re-submit ...</p>"
            if not user.end_mid: # first failure 
                user.end_mid = get_current_microversion(user)
                user.save() 
                return fail_msg, True 
            else: 
                return fail_msg, False
        else: # pass 
            # Update database to record success 
            time_spent = (timezone.now() - user.last_start).total_seconds()
            feature_cnt = feature_cnt
            end_mid = get_current_microversion(user)

            self.completion_count += 1
            self.completion_time.append(time_spent)
            self.completion_feature_cnt.append(feature_cnt)
            if user.is_reviewer: 
                self.reviewer_completion_count += 1
            self.save()

            user.end_mid = end_mid
            user.is_modelling = False 
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

    def give_up(self, user:AuthUser) -> Tuple[str, bool]: 
        """ The user gives up on the problem, no solutions to be provided yet 
        Returns: Tuple[message, ?collect_data]
        """
        temp_mid = get_current_microversion(user) 
        msg = "<p>To view the solution, please visit the source document to view the reference part.</p>"
        
        # Determine if data miner should collect data 
        if user.end_mid: # if at least one meaningful attempt evaluated before 
            time_spent = (timezone.now() - user.last_start).total_seconds()
            if str(self) in user.failure_history: 
                user.failure_history[str(self)].append((
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent
                ))
            else: 
                user.failure_history[str(self)] = [(
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent
                )]
            user.end_mid = temp_mid
            user.save() 
            return msg, True 
        else: 
            return msg, False 

    
    def show_result(self, user: AuthUser, show_best=False) -> str: 
        """ Other than the default time spent comparison, also plot the 
        distribution of features used to complete the question. 
        """
        if show_best: 
            my_fea_cnt = sorted(user.completed_history[str(self)], key=lambda x:x[1])[0][2] 
        else: 
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
        return super().show_result(user, show_best=show_best) + output

    def save(self, *args, **kwargs): 
        self.question_type = QuestionType.ASSEMBLY
        self.etype = ElementType.ASSEMBLY
        self.allowed_etype = ElementType.ASSEMBLY
        self.is_multi_step = False 
        # Get reference geometries 
        if not self.model_inertia: 
            mass_prop = get_mass_properties(
                self.did, "v", self.vid, self.eid, self.etype, 
                auth_token=get_admin_token(), massAsGroup=True
            )
            if mass_prop: 
                self.model_inertia = mass_prop['principalInertia']
            self.save() 
        return super().save(*args, **kwargs)


class Question_MSPS(Question): 
    # Additional question information 
    is_multi_part = models.BooleanField(
        default=False, 
        help_text="Does this question contains multiple parts in one Part Studio?"
    )
    starting_eid = models.CharField(
        "Starting element ID", 
        max_length=40, default=None, null=True, 
        help_text="(Optional) Starting part studio that need to be imported to user document with derived features. Leave blank if none is required."
    )
    init_mid = models.CharField(
        max_length=40, default=None, null=True, 
        help_text="Last microversion of the starting element's version"
    )

    # Additional analytics to be collected and presented 
    completion_feature_cnt = models.JSONField(
        default=list, help_text="List of feature counts required by users in history"
    )

    class Meta: 
        verbose_name = "Multi-step Part Studio Question"

    def publish(self) -> None:
        if self.is_published: 
            self.is_published = False 
        else: 
            # Check if necessary information is present 
            if (
                self.publishable() and (not self.starting_eid or self.init_mid) and 
                len(Question_Step_PS.objects.filter(question=self)) > 0
            ): 
                self.is_published = True 
        self.save() 
        return None 

    def initiate_actions(self, user: AuthUser) -> bool:
        """ Initiating actions are required to import starting parts to the user's 
        document with derived features when they start the question. 
        Return True if successful, otherwise False 
        """
        if not self.starting_eid: # no initial import required 
            return True 
        # Insert the all starting parts from the starting document to user's working 
        # document as one derived part 
        response = insert_ps_to_ps(
            user, self.did, self.vid, self.starting_eid, self.init_mid, 
            "Derived Starting Parts"
        )
        if not response: 
            return False 
        else: 
            # Store the import derived feature ID for evaluation 
            user.add_field = {"Cached_Derived_ID": response}
            user.save()
            return True

    def evaluate(self, user: AuthUser, step: int) -> Union[Tuple[str, bool], bool, int]:
        """ Given the user submiting a model for evaluation, this function checks if the 
        user model matches the reference model. 
        - If evaluation passed, True is returned. 
        - If evaluation cannot proceed due to API errors, False is returned. 
        - If evaluation found mismatch, a table showing the difference is returned to 
          be displayed in the HTML page. Returns: Tuple[err_message, ?collect_fail_data]
        """
        curr_step = Question_Step_PS.objects.filter(question=self).get(step_num=step)
        response = curr_step.evaluate(user)
        if not response: # API call failed 
            return False 
        elif type(response) is bool: # pass the evaluation 
            if step == len(Question_Step_PS.objects.filter(question=self)): # all steps completed 
                return True 
            else: # continue with next step 
                return step + 1
        else: # failed the evaluation  
            return response, False 
        

    def give_up(self, user: AuthUser, step: int) -> Tuple[str, bool]:
        """ After at least one failed attempt, the user is given the option to 
        give up, and reference part(s) will be derived imported to the user's 
        working document along with instructions
        Returns: Tuple[message, ?collect_data]
        """
        curr_step = Question_Step_PS.objects.filter(question=self).get(step_num=step)
        temp_mid = get_current_microversion(user)
        response = curr_step.give_up(user)
        
        # Prepare instructions of using the solution 
        if not response: # insert derive fail 
            msg = '''
            <p>To view the solution, please visit the source document to view the reference part.</p>
            <p>Optional: you can also import the reference part(s) into your working Part Studio using the derived feature. Following instructions below, you can line up the reference parts to your own and visualize the difference.</p>
            '''
        else: 
            msg = "<p>The reference parts are imported into your working Part Studio. You can follow instructions below to line up the reference parts to your own and visualize the difference.</p>"
            
        # Record basic data for database stats 
        if user.end_mid: # at least one meaningful attempt evaluated before 
            time_spent = (timezone.now() - user.last_start).total_seconds()
            if str(self) in user.failure_history: 
                user.failure_history[str(self)].append((
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent
                ))
            else: 
                user.failure_history[str(self)] = [(
                    datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S'), 
                    time_spent
                )]
            user.end_mid = temp_mid
            user.save() 
        return msg, False 

    def show_result(self, user: AuthUser, show_best=False) -> str:
        """ Other than the default time spent comparison, also plot the 
        distribution of features used to complete the question. 
        """
        if show_best: 
            my_fea_cnt = sorted(user.completed_history[str(self)], key=lambda x:x[1])[0][2] 
        else: 
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
        return super().show_result(user, show_best=show_best) + output

    def save(self, *args, **kwargs):
        self.question_type = QuestionType.MULTI_STEP_PS
        self.etype = ElementType.PARTSTUDIO
        self.allowed_etype = ElementType.PARTSTUDIO
        self.is_multi_step = True 
        # Get starting element's microversion ID 
        if self.starting_eid and not self.init_mid: 
            ele_info = get_elements(
                self, auth_token=get_admin_token(), elementId=self.starting_eid
            )
            if ele_info: 
                self.init_mid = ele_info[0]['microversionId'] 
        return super().save(*args, **kwargs)

    
class Question_Step_PS(models.Model): 
    question = models.ForeignKey(Question_MSPS, on_delete=models.CASCADE)
    step_number = models.PositiveIntegerField(default=1)
    eid = models.CharField("Onshape element ID", max_length=40, default=None)
    mid = models.CharField(
        max_length=40, default=None, null=True, 
        help_text="Last microversion of the reference element's version"
    )
    
    class Meta: 
        verbose_name = "MSPS Question Step"
    
    # Properties for evaluation 
    model_mass = models.JSONField(default=list, null=True, help_text="Mass in kg")
    model_volume = models.JSONField(default=list, null=True, help_text="Volume in m^3")
    model_SA = models.JSONField(default=list, null=True, help_text="Surface area in m^2")
    model_inertia = models.JSONField(default=list, null=True, help_text="3 element array describing the Principal Interia") 

    def evaluate(self, user: AuthUser) -> Union[str, bool]:
        """ Given the user submiting a model for evaluation, this function checks if the 
        user model matches the reference model. 
        - If evaluation passed, True is returned. 
        - If evaluation cannot proceed due to API errors, False is returned. 
        - If evaluation found mismatch, error message is returned to 
          be displayed in the HTML page. 
        """
         # Get info from user model 
        feature_list = get_feature_list(user)
        mass_prop = get_mass_properties(
            user.did, "w", user.wid, user.eid, user.etype, 
            massAsGroup=bool(not self.question.is_multi_part), 
            auth_token=user.access_token
        )
        if not feature_list or not mass_prop: # API call failed 
            return False 

        # Check if there are derived features 
        for fea in feature_list['features']: 
            if (
                fea['featureType'] == 'importDerived' and 
                (not self.question.starting_eid or fea['featureId'] != user.add_field['Cached_Derived_ID'])
            ): 
                return "It is detected that your model contains derived features through import. Please complete the task with native Onshape features only and resubmit for evaluation ..." 
        
        # Check if submitted parts are okay with basic metrics 
        if len(mass_prop['bodies']) == 0: 
            return "No parts found - please model the part then try re-submitting." 
        elif self.question.is_multi_part and not mass_prop['bodies']['-all-']['hasMass']: 
            return "Please remember to assign a material to your part."
        elif (
            not self.question.is_multi_part and 
            len(mass_prop['bodies']) != len(self.model_mass)
        ): # Check num of parts 
            return "The number of parts in your Part Studio does not match the reference Part Studio." 
        
        # Compare property values 
        if self.question.is_multi_part: 
            eval_correct = multi_part_geo_check(
                self, 
                [
                    [prt['mass'][0] for prt in mass_prop['bodies'].values()], 
                    [prt['volume'][0] for prt in mass_prop['bodies'].values()], 
                    [prt['periphery'][0] for prt in mass_prop['bodies'].values()], 
                    [prt['principalInertia'][0] for prt in mass_prop['bodies'].values()]
                ]
            )
        else: 
            eval_correct = single_part_geo_check(
                self, 
                [
                    mass_prop['bodies']['-all-']['mass'][0], 
                    mass_prop['bodies']['-all-']['volume'][0], 
                    mass_prop['bodies']['-all-']['periphery'][0],
                    mass_prop['bodies']['-all-']['principalInertia'][0]
                ]
            )
        if type(eval_correct) is bool: # geo check passed 
            return True 
        else: 
            return eval_correct 

    def give_up(self, user: AuthUser) -> bool: 
        """ When give up, import the derived reference part of the step to the 
        user's working document 
        Return True if successful, False otherwise 
        """
        response = insert_ps_to_ps(
            user, self.question.did, self.question.vid, self.eid, self.mid, 
            "Derived Reference Part"
        )
        if response: 
            return True 
        else: 
            return False 
        
    def save(self, *args, **kwargs):
        if not self.mid: 
            ele_info = get_elements(
                self, auth_token=get_admin_token(), elementId=self.eid
            )
            if ele_info: 
                self.mid = ele_info[0]["microversionId"]
        return super().save(*args, **kwargs)


#################### Helper API calls ####################
_Q_TYPES = Union[
    Question_SPPS, Question_MPPS, Question_ASMB, Question_MSPS
] # for function argument hints 


def get_admin_token() -> str: 
    """ Get a token (refresh if needed) from one of the main admins, 
    as defined in the Reviewer model, to complete question management 
    related actions 
    """
    # Get one main admin user 
    try: 
        admin_user = AuthUser.objects.get(
            os_user_id=Reviewer.objects.filter(is_main_admin=True)[0].os_user_id
        )
    except Exception: 
        raise ValidationError("No main admin users have been assigned from the reviewers yet.")
    # Refresh token if needed 
    if admin_user.expires_at < timezone.now() + timedelta(hours=1): 
        admin_user.refresh_oauth_token() 
    return admin_user.access_token


def get_thumbnail(question: _Q_TYPES, auth_token: str) -> str: 
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
            "Authorization": "Bearer " + auth_token
        }
    )
    
    if response.ok: 
        return f"data:image/png;base64,{response.json()['images'][0]}"
    else: 
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABmJLR0QA/wD/AP+gvaeTAAAAy0lEQVRIie2VXQ6CMBCEP7yDXkEjeA/x/icQgrQcAh9czKZ0qQgPRp1kk4ZZZvYnFPhjJi5ABfRvRgWUUwZLxIe4asEsMOhndmzhqbtZSdDExxh0EhacRBIt46V5oJDwEd4BuYQjscc90ATiJ8UfgFvEXPNNqotCKtEvF8HZS87wLAeOijeRTwhahsNoWmVi4pWRhLweqe4qCp1kLVUv3UX4VgtaX7IXbmsU0knuzuCz0SEwWIovvirqFTSrKbLkcZ8v+RecVyjyl3AHdAl3ObMLisAAAAAASUVORK5CYII="


def get_jpeg_drawing(question: _Q_TYPES, auth_token: str) -> str: 
    """ Get the JPEG version of the drawing to be displayed when modelling 
    """
    response = requests.get(
        "https://cad.onshape.com/api/blobelements/d/{}/v/{}/e/{}".format(
            question.did, question.vid, question.jpeg_drawing_eid
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/octet-stream;charset=UTF-8;qs=0.09", 
            "Authorization" : "Bearer " + auth_token
        }
    )
    
    if response.ok: 
        response = base64.b64encode(response.content)
        return f"data:image/jpeg;base64,{response.decode('ascii')}"
    else: 
        return "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABgAAAAYCAYAAADgdz34AAAABmJLR0QA/wD/AP+gvaeTAAAAy0lEQVRIie2VXQ6CMBCEP7yDXkEjeA/x/icQgrQcAh9czKZ0qQgPRp1kk4ZZZvYnFPhjJi5ABfRvRgWUUwZLxIe4asEsMOhndmzhqbtZSdDExxh0EhacRBIt46V5oJDwEd4BuYQjscc90ATiJ8UfgFvEXPNNqotCKtEvF8HZS87wLAeOijeRTwhahsNoWmVi4pWRhLweqe4qCp1kLVUv3UX4VgtaX7IXbmsU0knuzuCz0SEwWIovvirqFTSrKbLkcZ8v+RecVyjyl3AHdAl3ObMLisAAAAAASUVORK5CYII="


def get_mass_properties(
    did: str, wvm: str, wvmid: str, eid: str, etype: str, auth_token: str, massAsGroup=True
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
            "Authorization" : "Bearer " + auth_token
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


def get_current_microversion(user: AuthUser) -> Union[str, None]: 
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


def get_elements(question: _Q_TYPES, auth_token: str, elementId=None) -> Any: 
    """ Get all elements in a document's version and their information 
    """
    response = requests.get(
        "https://cad.onshape.com/api/documents/d/{}/v/{}/elements".format(
            question.did, question.vid
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
            "Authorization" : "Bearer " + auth_token
        }, 
        params={
            "elementId": elementId
        }
    )
    if response.ok: 
        return response.json() 
    else: 
        return [] 


def insert_ps_to_ps(
    user: AuthUser, source_did: str, source_vid: str, source_eid: str, source_mid: str, 
    derive_feature_name: str
) -> Optional[str]: 
    """ Insert the entire source part studio into the user's (target) 
    part studio with one PS derived feature. 
    
    Returns: 
        The featureId of the successfully created derived feature; 
        None otherwise. 
    """
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
                "name": derive_feature_name,
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
                            source_did, source_vid, source_eid, source_mid
                        ),
                        "imports": []
                    }
                ],
                "featureType": "importDerived"
            }
        }
    )
    if not response.ok: 
        return None
    else: 
        # Return the import derived feature ID 
        return response.json()['feature']['featureId']


def create_assembly_instance(
    user: AuthUser, s_did: str, s_vid: str, s_eid: str
) -> bool: 
    """ Insert all parts from a part studio (version) to a working assembly as 
    instances 
    """
    response = requests.post(
        os.path.join(
            user.os_domain, 
            "api/assemblies/d/{}/w/{}/e/{}/instances".format(
                user.did, user.wid, user.eid
            )
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
            "Authorization" : "Bearer " + user.access_token
        }, 
        json={
            'documentId': s_did, 
            'versionId': s_vid, 
            'elementId': s_eid, 
            'isWholePartStudio': True 
        }
    )
    if response.ok: 
        return True 
    else: 
        return False 


def get_assembly_definition(user: AuthUser, includeMateFeatures=True) -> Any: 
    response = requests.get(
        os.path.join(
            user.os_domain, 
            "api/assemblies/d/{}/w/{}/e/{}".format(
                user.did, user.wid, user.eid
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


def single_part_geo_check(
    question: Union[Question_SPPS, Question_Step_PS], user_prop: Iterable[Any], err_tol=0.005
) -> Union[bool, str]: 
    """ The model is considered to be correct if all properties of the user's model 
    falls within the properties of the reference model ± err_tol. 
    Returns True if check is passed; otherwise, an HTML table of comparison is returned 
    """
    ref_prop = [
        question.model_mass, question.model_volume, question.model_SA, 
        question.model_inertia[0]
    ]
    check_symbols = [] 
    check_pass = True 
    
    for i, item in enumerate(ref_prop): 
        # Check for accuracy 
        if (
            item * (1 - err_tol) > user_prop[i] or 
            user_prop[i] > item * (1 + err_tol)
        ): 
            check_pass = False 
            check_symbols.append("&#x2717;")
        else: 
            check_symbols.append("&#x2713;")
        # Round for display 
        if item < 0.1 or item > 99: 
            ref_prop[i] = '{:.2e}'.format(ref_prop[i])
            user_prop[i] = '{:.2e}'.format(user_prop[i])
        else: 
            ref_prop[i] = round(ref_prop[i], 3)
            user_prop[i] = round(user_prop[i], 3)
    
    if check_pass: 
        return True 
    else: 
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
                <td>{ref_prop[i]}</td>
                <td>{user_prop[i]}</td>
                <td>{check_symbols[i]}</td>
            </tr>
            '''
        return fail_msg + "</table>"


def multi_part_geo_check(
    question: Union[Question_MPPS, Question_Step_PS], user_prop: Iterable[Any], 
    err_tol=0.005
) -> Union[bool, str]: 
        """ The model is considered to be correct if for every part in the reference model, 
        there is one and only one part in the user's model with matching properties. 
        Limitation: avoid having parts with properties that are too closed numerically. 
        """
        ref_prop = [
            question.model_mass, question.model_volume, question.model_SA, 
            [val[0] for val in question.model_inertia]
        ]
        ref_prop = sorted(
            [
                (ref_prop[0][i], ref_prop[1][i], ref_prop[2][i], ref_prop[3][i]) 
                for i in range(len(ref_prop[0]))
            ], 
            key=lambda x : x[0]
        )
        user_prop = sorted(
            [
                (user_prop[0][i], user_prop[1][i], user_prop[2][i], user_prop[3][i]) 
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