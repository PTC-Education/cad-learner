import os 
import requests
from datetime import timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse 
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, HttpResponseNotFound
from django.utils import timezone 
from django.utils.datastructures import MultiValueDictKeyError
from django.core.exceptions import ObjectDoesNotExist

from .models import AuthUser, Question, Question_SPPS, Question_MPPS, QuestionType
from data_miner.views import collect_fail_data, collect_final_data


Q_Type_Dict = {
    QuestionType.SINGLE_PART_PS: Question_SPPS, 
    QuestionType.MULTI_PART_PS: Question_MPPS
}


# Create your views here.
def login(request: HttpRequest): 
    """ When the app extension is first opened, this view should 
    be called. 
    -   If user is within the allowed modelling time span, redirects 
        to the modelling page to continue 
    -   If new user, redirects the user to initiate Onshape's OAuth
        authorization 
    """
    if request.GET.get("wvm") != 'w': 
        return HttpResponse("Please relaunch this app in the main workspace or create a branch from the left panel to start modelling ...")

    user_id = request.GET.get('userId')
    try: 
        user = AuthUser.objects.get(os_user_id=user_id)
        # Check if user is modelling 
        if (
            user.modelling and 
            user.last_start + timedelta(hours=1) < timezone.now() and 
            user.eid == request.GET.get('eid')
        ): 
            # Refresh token if needed 
            if user.expires_at < timezone.now() + timedelta(hours=1): 
                user.refresh_oauth_token() 
            # Redirect to modelling page 
            return HttpResponseRedirect(reverse(
                "questioner:modelling", 
                args=[user.curr_question_type, user.curr_question_id, user.os_user_id]
            )) 
    except ObjectDoesNotExist: 
        # Create a new user 
        user = AuthUser(os_user_id=user_id)
    
    user.os_domain = request.GET.get('server')
    user.did = request.GET.get('did')
    user.wid = request.GET.get('wvmid')
    user.eid = request.GET.get('eid')
    user.etype = request.GET.get('etype')
    user.save() 

    return redirect(
        os.path.join(
            os.environ['OAUTH_URL'], 
            "oauth/authorize"
        ) + "?response_type=code&client_id={}".format(
            os.environ['OAUTH_CLIENT_ID'].replace('=', '%3D')
        )
    )


def authorize(request: HttpRequest): 
    """ When the user authorizes the OAuth integration, Onshape's OAuth 
    authorization page will redirect the user to this page, as registered 
    as the redirect URL. 
    """
    try: 
        auth_code = request.GET.get('code')
    except MultiValueDictKeyError: 
        return HttpResponse(
            "User authentication failed!\nError: " + str(
                request.GET.get('error')
            )
        )
    
    # Use the authorization code to get access token and refresh token 
    token_response = requests.post(
        os.path.join(
            os.environ['OAUTH_URL'], 
            "oauth/token"
        ) + "?grant_type=authorization_code&code={}&client_id={}&client_secret={}".format(
            auth_code.replace('=', '%3D'), 
            os.environ['OAUTH_CLIENT_ID'].replace('=', '%3D'), 
            os.environ['OAUTH_CLIENT_SECRET'].replace('=', '%3D')
        ), 
        headers={'Content-Type': "application/x-www-form-urlencoded"}
    ).json() 
    
    # Use the sessioninfo API request to get the user's info 
    # for backend data storage 
    sess_response = requests.get(
        "https://cad.onshape.com/api/users/sessioninfo", 
        headers={"Authorization": "Bearer " + token_response['access_token']}
    ).json() 

    user = AuthUser.objects.get(os_user_id=sess_response['id'])
    user.access_token = token_response['access_token']
    user.refresh_token = token_response['refresh_token']
    user.expires_at = timezone.now() + timedelta(seconds=token_response['expires_in'])
    user.save() 

    return HttpResponseRedirect(reverse("questioner:index", args=[user.os_user_id]))


def index(request: HttpRequest, os_user_id: str): 
    """ The index view of the app. 
    It outlines all instructions and list all available practice models 
    in categories of difficulties. 
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    return render(
        request, "questioner/index.html", 
        context={
            "user": curr_user, 
            "questions": Question.objects.filter(published=True).order_by("question_name")
        }
    )


def model(request: HttpRequest, question_type: str, question_id: int, os_user_id: str): 
    """ The view that the users see when working on a question. 
    It provides all necessary information and instructions for the 
    question. When the user finishes, they should be able to submit 
    and check if model is correct. 
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    if question_type not in Q_Type_Dict.keys(): 
        return HttpResponseNotFound("Question type not found") 
    curr_que = get_object_or_404(Q_Type_Dict[question_type], question_id=question_id)
    
    # Check if the user is starting with an empty part studio or assembly 
    response = requests.get(
        os.path.join(
            curr_user.os_domain,
            "api/{}/d/{}/w/{}/e/{}/features".format(
                curr_user.etype, curr_user.did, curr_user.wid, curr_user.eid
            )
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
            "Authorization": "Bearer " + curr_user.access_token
        }
    )
    if response.ok: 
        response = response.json()
        if len(response['features']) > 0: 
            return render(
                request, "questioner/index.html", 
                context={
                    "user": curr_user, 
                    "questions": Question.objects.filter(published=True).order_by("question_name"), 
                    "error_message": "Please start with an empty part studio and relaunch this app ..."
                }
            )
    else: 
        return HttpResponse("An unexpected error has occurred. Please check internet connection and relaunch Onshape ...")

    # Run any start modelling process 
    curr_user.add_field = {} # clean field 
    curr_user.save() 
    initiate_succ = curr_que.initiate_actions(curr_user)
    if not initiate_succ: 
        return HttpResponse("Failed to start the question. Please relaunch the app and try again ...")

    # Okay to start modelling 
    curr_user.modelling = True 
    curr_user.last_start = timezone.now() 
    curr_user.curr_question_type = curr_que.question_type
    curr_user.curr_question_id = curr_que.question_id 
    curr_user.end_mid = None

    # Get current microversion ID 
    response = requests.get(
        os.path.join(
            curr_user.os_domain, 
            "api/documents/d/{}/w/{}/currentmicroversion".format(
                curr_user.did, curr_user.wid, curr_user.eid
            )
        ), 
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/vnd.onshape.v2+json;charset=UTF-8;qs=0.09", 
            "Authorization": "Bearer " + curr_user.access_token
        }
    )
    if response.ok: 
        response = response.json() 
        curr_user.start_mid = response['microversion']
    else: 
        curr_user.start_mid = None 
    curr_user.save() 

    return render(
        request, "questioner/modelling.html", 
        context={
            "user": curr_user, 
            "question": curr_que
        }
    )


def check_model(request: HttpRequest, question_type: str, question_id: int, os_user_id: str): 
    """ When a user submits a model, API calls are made to check if the 
    model is dimensionally correct and placed in proper orientation. 
    If the model is correct, redirect to the complete page. 
    If not correct, redirect back to the model page to ask for modifications. 
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    if question_type not in Q_Type_Dict.keys(): 
        return HttpResponseNotFound("Question type not found") 
    curr_que = get_object_or_404(Q_Type_Dict[question_type], question_id=question_id)

    response = curr_que.evaluate(curr_user)

    if not response: 
        return HttpResponse("An unexpected error has occurred. Please check internet connection and try relaunching the app in the part studio that you originally started this modelling question with ...")
    elif type(response) is bool: 
        # Initiate data collection from data miner 
        collect_final_data(curr_user)
        # Redirect to complete page 
        return HttpResponseRedirect(reverse(
            "questioner:complete", args=[
                curr_que.question_type, curr_que.question_id, curr_user.os_user_id
            ]
        ))
    else: 
        if response[1]: # initiate failure attempt collection 
            collect_fail_data(curr_user)
        return render(
            request, "questioner/modelling.html", 
            context={
                "user": curr_user, 
                "question": curr_que, 
                "model_comparison": response[0] # failure message 
            }
        )


def complete(request: HttpRequest, question_type: str, question_id: int, os_user_id: str): 
    """ THe view that the users see when a question is finished. 
    It provides a brief summary of the user's performance and relative 
    comparisons to all other users. Users should be able to return to 
    index page to start more practice. 
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    if question_type not in Q_Type_Dict.keys(): 
        return HttpResponseNotFound("Question type not found") 
    curr_que = get_object_or_404(Q_Type_Dict[question_type], question_id=question_id)

    return render(
        request, "questioner/complete.html", 
        context={
            "user": curr_user, 
            "question": curr_que, 
            "stats_display": curr_que.show_result(curr_user)
        }
    )