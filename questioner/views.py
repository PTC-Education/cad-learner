import os 
import datetime 
import requests

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse 
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils import timezone 
from django.utils.datastructures import MultiValueDictKeyError
from django.core.exceptions import ObjectDoesNotExist

from .models import AuthUser, Question


# Create your views here.
def login(request: HttpRequest): 
    """ When the app extension is first opened, this view should 
    be called. 
    -   If user is within the allowed modelling time span, redirects 
        to the modelling page 
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
            user.last_start + datetime.timedelta(minutes=90) < timezone.now() 
        ): 
            if user.expires_at < timezone.now + datetime.timedelta(hours=1): 
                user.refresh_oauth_token() 
            return HttpResponseRedirect(reverse(
                "questioner:modelling", args=[user.curr_question, user.os_user_id]
            )) 
    except ObjectDoesNotExist: 
        user = AuthUser(os_user_id=user_id)
    
    user.os_domain = request.GET.get('server')
    user.did = request.GET.get('did')
    user.wid = request.GET.get('wvmid')
    user.eid = request.GET.get('eid')

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
    user.expires_at = timezone.now() + datetime.timedelta(seconds=token_response['expires_in'])
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
            "questions": Question.objects.order_by("question_name")
        }
    )


def model(request: HttpRequest, question_name: str, os_user_id: str): 
    """ The view that the users see when working on a question. 
    It provides all necessary information and instructions for the 
    question. When the user finishes, they should be able to submit 
    and check if model is correct. 
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    curr_que = get_object_or_404(Question, question_name=question_name)
    return render(
        request, "question/model.html", 
        context={
            "user": curr_user, 
            "question": curr_que
        }
    )


def complete(request: HttpRequest, question_name: str, os_user_id: str): 
    """ THe view that the users see when a question is finished. 
    It provides a brief summary of the user's performance and relative 
    comparisons to all other users. Users should be able to return to 
    index page to start more practice. 
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    curr_que = get_object_or_404(Question, question_name=question_name)
    return render(
        request, "question/complete.html", 
        context={
            "user": curr_user, 
            "question": curr_que
        }
    )
