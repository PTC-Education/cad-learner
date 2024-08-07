import os 
import requests
from math import floor
from datetime import timedelta, date
from typing import Union 
from PIL import Image, ImageDraw, ImageFont

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse 
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, HttpResponseNotFound
from django.utils import timezone 
from django.utils.datastructures import MultiValueDictKeyError
from django.core.exceptions import ObjectDoesNotExist
from django.conf import settings

from .models import * 
from data_miner.views import collect_fail_data, collect_final_data, collect_multi_step_data


Q_Type_Dict = {
    QuestionType.SINGLE_PART_PS: Question_SPPS, 
    QuestionType.MULTI_PART_PS: Question_MPPS, 
    QuestionType.ASSEMBLY: Question_ASMB, 
    QuestionType.MULTI_STEP_PS: Question_MSPS
}
_Q_TYPES_HINT = Union[Question_SPPS, Question_MPPS, Question_ASMB, Question_MSPS]


def should_collect_data(user: AuthUser, question: _Q_TYPES_HINT) -> bool: 
    """ Storage space is expensive, and using the data_miner takes up space. 
    This function sets the criteria on intiation of data collection with the 
    data_miner. 
    """
    # Max number of data entries to be collected for every question 
    MAX_ENTRIES_PER_QUESTION = 250 
    # Max number of data entries to be collected for every user on the same question 
    MAX_ENTRIES_PER_USER = 3
    # After the MAX_ENTRIES_PER_USER, new data are collected for a user iff the time spent 
    # has improvement over the best performance in history by a factor of MIN_IMPROV_REQ  
    MIN_IMPROVE_REQ = 0.2
    
    if (
        not question.is_published or 
        not question.is_collecting_data or 
        question.completion_count > MAX_ENTRIES_PER_QUESTION
    ): 
        return False 
    
    try: 
        user_hist = user.completed_history[str(question)]
    except KeyError: # no history yet 
        return True 
    if len(user_hist) > MAX_ENTRIES_PER_USER: 
        best_perf = min([item[1] for item in user_hist[:-1]])
        if user_hist[-1][1] > best_perf * (1 - MIN_IMPROVE_REQ): 
            return False 
    
    return True 


# Create your views here.
def home(request: HttpRequest, os_user_id=None):
    """ 
    The home page that can be accessed either logged in in-app or as a standard URL without login information. 
    
    The page documents more extensive user instructions, some technical tips, and a documentation on all data collections from the users. 

    **Arguments:**
        
    - ``os_user_id``: (Optional) identify the :model:`questioner.AuthUser` model with the user's login information.

    **Template:**

    :template:`questioner/home.html`
    """
    context = {"user": None} 
    if os_user_id: 
        curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
        context['user'] = curr_user
    return render(request, "questioner/home.html", context=context)


def login(request: HttpRequest): 
    """ 
    When the app extension is first opened, this view should be called. 

    **Context:**
    
    If new user, redirects the user to initiate Onshape's OAuth authorization. Once authenticated, the user will be redirected back to :view:`questioner.views.authorize`.  
    
    - A new :model:`questioner.AuthUser` model will be created for the new user with the user's ``os_user_id``. 
    
    - If the user already exists, new Onshape working environment IDs will be recorded. 
    
    If user is modelling and still within the allowed modelling time span and the same working space, redirects the user directly to the modelling page (:view:`questioner.views.model`) of the question to continue. 
    """
    if request.GET.get("wvm") != 'w': 
        return HttpResponse("Please relaunch this app in the main workspace or create a branch from the left panel to start modelling ...")

    user_id = request.GET.get('userId')
    try: 
        user = AuthUser.objects.get(os_user_id=user_id)
        # Check if user is modelling 
        if (
            user.is_modelling and 
            user.last_start + timedelta(hours=1) >= timezone.now() and 
            user.eid == request.GET.get('eid')
        ): 
            # Refresh token if needed 
            if user.expires_at < timezone.now() + timedelta(hours=1): 
                user.refresh_oauth_token() 
            # Redirect to modelling page 
            args=[user.curr_question_type, user.curr_question_id, user.os_user_id, 0]
            # Check if multi-step 
            if Q_Type_Dict[user.curr_question_type].objects.get(
                question_id=user.curr_question_id
            ).is_multi_step: 
                args.append(user.curr_step)
            return HttpResponseRedirect(reverse(
                "questioner:modelling", 
                args=args
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
    """ 
    When the user authorizes the OAuth integration, Onshape's OAuth authorization page will redirect the user to this page, as registered as the redirect URL. 
    
    Once all necessary registration of the returned tokens is done by the app, the user will be redirected to :view:`questioner.views.index`. 
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


def create_cert_png(curr_user, base64_jpeg_data, cert_date):
    static_dir = 'questioner' + settings.STATIC_URL + 'questioner/'
    font_path = os.path.join(static_dir, 'fonts', 'Raleway-Medium.ttf')
    print(cert_date)
    if base64_jpeg_data.startswith('data:image/jpeg;base64,'):
        base64_jpeg = base64_jpeg_data[len('data:image/jpeg;base64,'):]
    try:
        # Decode the base64 string into bytes
        jpeg_bytes = base64.b64decode(base64_jpeg)
        print("Base64 string successfully decoded")
        try:
            img = Image.open(io.BytesIO(jpeg_bytes))
            draw = ImageDraw.Draw(img)
            user_name = get_user_name(curr_user)
            # Add text to the image
            certW = 3300
            date_arr = cert_date.split(' ', 1)[0].split('-')
            date_text = date_arr[1] + "-" + date_arr[2] + "-" + date_arr[0]
            name_font = ImageFont.truetype(font_path, 150)
            cert_font = ImageFont.truetype(font_path, 100)
            nameW, h = draw.textsize(user_name, font=name_font)
            dateW, h = draw.textsize(date_text, font=cert_font)
            name_pos = ((certW-nameW)/2, 1260)
            date_pos = ((certW-dateW)/2, 2075)
            date_color = (51, 51, 51)
            name_color = (64, 170, 29)
            draw.text(name_pos, user_name, font=name_font, fill=name_color, stroke_width=2, stroke_fill=name_color)
            draw.text(date_pos, date_text, font=cert_font, fill=date_color)
            img_io = io.BytesIO()
            img.save(img_io, 'PNG')
            print("successfully converted to png")
            img_base64 = base64.b64encode(img_io.getvalue()).decode('utf-8')
            return img_base64
        except Exception as e:
            print(f"Error opening image: {e}")
            return HttpResponse(f"Error opening image: {e}", status=400)
    except Exception as e:
        print(f"General error: {e}")
        return HttpResponse(f"Error converting image: {str(e)}", status=500)
      
def dashboard(request: HttpRequest, os_user_id: str):
    """ 
    User Dashboard
    - Challenge history
    - Certificate progress

    **Arguments:**
    - ``os_user_id``: identify the :model:`questioner.AuthUser` model with the user's login information.

    **Template:**
    :template:`questioner/dashboard.html`
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    difficulty_count = {'EA':0,'ME':0,'CH':0}
    types_count = {'SPPS':0,'MPPS':0,'MSPS':0,'ASMB':0}

    certificates = []

    # certificates array for each certificate [certname, [completed challenges], [incompleted challenges], cert_id, cert_date]
    for certificate in Certificate.objects.order_by('certificate_name'):
        base_jpeg = certificate.drawing_jpeg
        certificates.append([certificate.certificate_name,[],certificate.required_challenges, certificate.id, "", certificate.is_published])
    
    for key in curr_user.completed_history:
        num = key.split('_')[1]
        chall_type = key.split('_')[0]
        try:
            difficulty_count[Question.objects.filter(question_id=num).values('difficulty')[0]['difficulty']] += 1
            types_count[chall_type] += 1
        except:
            pass
        
        for i, cert in enumerate(certificates):
            if int(num) in cert[2]:
                certificates[i][2].remove(int(num))
                certificates[i][1].append(int(num))

        for i,attempt in enumerate(curr_user.completed_history[key]):
            curr_user.completed_history[key][i][1] = "{} min {} sec".format(
            int(attempt[1] // 60), int(attempt[1] % 60)
        )
    
    dates = []
    for i, cert in enumerate(certificates):
        if len(cert[2]) == 0:
            for key, value in curr_user.completed_history.items():
                num = int(key.split('_')[1])
                if num in cert[1]:
                    for cert_date in value:
                        dates.append(cert_date[0])
            dates.sort(reverse=True)
            certificates[i][3] = cert[3]
            certificates[i][4] = dates[0]

    context = {"user": curr_user}
    context["questions"] = Question.objects.order_by("question_name")
    context["difficulty_count"] = difficulty_count
    context["types_count"] = types_count
    context["total_count"] = len(curr_user.completed_history.keys())
    context["certificates"] = certificates

    return render(request, "questioner/dashboard.html", context=context)

def certificate(request: HttpRequest, os_user_id: str, cert_id: int, cert_date: str):
    """ 
    Certificate display

    **Arguments:**
    - ``os_user_id``: identify the :model:`questioner.AuthUser` model with the user's login information.

    **Template:**
    :template:`questioner/certificate.html`
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)

    try:
        certificate = Certificate.objects.get(id=cert_id)
        base_jpeg = certificate.drawing_jpeg
    except Certificate.DoesNotExist:
        print(f"Certificate with id {cert_id} does not exist.")

    cert_image = create_cert_png(curr_user, base_jpeg, cert_date)

    context = {"cert_image": cert_image}

    return render(request, "questioner/certificate.html", context=context)

def index(request: HttpRequest, os_user_id: str): 
    """ 
    The index view of the app that presents all available questions. 
    
    **Context:**
    
    It outlines all instructions and lists all available questions (:model:`questioner.Question`) with filters of categories in difficulties and types. 
    
    If the user is a reviewer, unpublished questions are also presented with an additional filter of availability. 
    
    **Arguments:**
    
    - ``os_user_id``: identify the :model:`questioner.AuthUser` model with the user's login information and reviewer status. 
    
    **Template:**
    
    :template:`questioner/index.html`
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)

    certs = {}
    for certificate in Certificate.objects.order_by('certificate_name'):
        certs[certificate.certificate_name] = certificate.required_challenges

    context = {"user": curr_user}
    if curr_user.is_reviewer: 
        context["questions"] = Question.objects.order_by("question_name")
    else: 
        context["questions"] = Question.objects.filter(is_published=True).order_by("question_name")

    cert_type_map = {}
    for cert_type, ids in certs.items():
        for question_id in ids:
            cert_type_map[question_id] = cert_type

    for question in context['questions']:
        question.cert_type = cert_type_map.get(question.question_id, None)

    return render(request, "questioner/index.html", context=context)


def model(request: HttpRequest, question_type: str, question_id: int, os_user_id: str, initiate: int, step=1): 
    """ 
    The view that the users see when working on a question. 
    
    **Context:**
    
    It initiates a question and provides all necessary information and instructions for the question. 
    
    When the user finishes, they should be able to submit for evaluation of model correctness, which redirects to :view:`questioner.check_model`. 
    
    **Arguments:**
    
    - ``question_type``: one of the supported question type model inheriting :model:`questioner.Question`  
    - ``question_id``: the unique ID of the question 
    - ``os_user_id``: the unique ID linked to the user's :model:`questioner.AuthUser` profile 
    - ``initiate``: 1 (True) if starting (initiating) a new question; 0 (False) if reopening the Onshape extension panel while modelling 
    - ``step``: only applicable to multi-step questions (index starts from 1)
    
    **Template:**
    
    :template:`questioner/modelling.html`
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    if question_type not in Q_Type_Dict.keys(): 
        return HttpResponseNotFound("Question type not found") 
    curr_que = get_object_or_404(Q_Type_Dict[question_type], question_id=question_id)
    
    if initiate: 
        # Refresh token if needed 
        if curr_user.expires_at < timezone.now() + timedelta(hours=1): 
            curr_user.refresh_oauth_token() 
        
        # Check if the user is starting with an empty part studio or assembly 
        if curr_user.etype == ElementType.PARTSTUDIO: 
            response = get_feature_list(curr_user)
            if response: 
                if len(response['features']) > 0: 
                    context = {
                        "user": curr_user, 
                        "error_message": "Please start with an empty part studio and relaunch this app ..."
                    }
                    if curr_user.is_reviewer: 
                        context["questions"] = Question.objects.order_by("question_name")
                    else: 
                        context["questions"] = Question.objects.filter(is_published=True).order_by("question_name")
                    return render(request, "questioner/index.html", context=context)
            else: 
                return HttpResponse("An unexpected error has occurred. You may have lost your internet connection or granted OAuth access to the wrong Onshape account/Enterprise. Please refresh the page and relaunch the app ...")
        elif curr_user.etype == ElementType.ASSEMBLY: 
            response = get_assembly_definition(curr_user)
            if response: 
                if (
                    response["parts"] or 
                    response['rootAssembly']['instances'] or 
                    response['rootAssembly']['features'] or 
                    response['subAssemblies']
                ): 
                    context = {
                        "user": curr_user, 
                        "error_message": "Please start with an empty assembly and relaunch this app ..."
                    }
                    if curr_user.is_reviewer: 
                        context["questions"] = Question.objects.order_by("question_name")
                    else: 
                        context["questions"] = Question.objects.filter(is_published=True).order_by("question_name")
                    return render(request, "questioner/index.html", context=context)
            else: 
                return HttpResponse("An unexpected error has occurred. You may have lost your internet connection or granted OAuth access to the wrong Onshape account/Enterprise. Please refresh the page and relaunch the app ...")
        else: 
            return HttpResponse("Unrecognized element type. Please relaunch the app in a Part Studio or an Assembly ...")

        # Run any start modelling process 
        curr_user.add_field = {} # clean field 
        curr_user.save() 
        initiate_succ = curr_que.initiate_actions(curr_user)
        if not initiate_succ: 
            return HttpResponse("Failed to start the question. Please relaunch the app and try again ...")

        # Okay to start modelling 
        curr_user.is_modelling = True 
        curr_user.last_start = timezone.now() 
        curr_user.curr_question_type = curr_que.question_type
        curr_user.curr_question_id = curr_que.question_id 
        curr_user.end_mid = None
        curr_user.curr_step = 1

        # Get current microversion ID 
        curr_user.start_mid = get_current_microversion(curr_user)
        curr_user.save() 
    
    if step > 1: 
        curr_user.curr_step = step 
        curr_user.save() 
        
    context={
        "user": curr_user, 
        "question": curr_que
    }
    if curr_que.is_multi_step:
        context["step"] = Question_Step_PS.objects.filter(
            question=curr_que
        ).get(step_number=step)
    
    return render(
        request, "questioner/modelling.html", 
        context=context
    )


def check_model(request: HttpRequest, question_type: str, question_id: int, os_user_id: str, step=1): 
    """ 
    When a user submits a model, API calls are made to check if the 
    model is dimensionally correct and placed in proper orientation. 
    
    **Context:**
    
    If the model is correct, redirect to :view:`questioner.complete`. 
    
    If not correct, re-render the modelling page with evaluation feedback and ask for modifications before re-submission. 
    
    - User is also then given the option to give-up, which redirects them to :view:`questioner.solution`. 
    
    **Arguments:**
    
    - ``question_type``: one of the supported question type model inheriting :model:`questioner.Question`  
    - ``question_id``: the unique ID of the question 
    - ``os_user_id``: the unique ID linked to the user's :model:`questioner.AuthUser` profile 
    - ``step``: only applicable to multi-step questions (index starts from 1)
    
    **Template:**
    
    :template:`questioner/modelling.html`
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    if question_type not in Q_Type_Dict.keys(): 
        return HttpResponseNotFound("Question type not found") 
    curr_que = get_object_or_404(Q_Type_Dict[question_type], question_id=question_id)

    # Refresh token if needed 
    if curr_user.expires_at < timezone.now() + timedelta(minutes=20): 
        curr_user.refresh_oauth_token() 
    
    if curr_que.is_multi_step: 
        response = curr_que.evaluate(curr_user, step)
    else: 
        response = curr_que.evaluate(curr_user)

    if not response: # API error 
        return HttpResponse("An unexpected error has occurred. Please check internet connection and try relaunching the app in the part studio that you originally started this modelling question with ...")
    elif type(response) is bool: # Submission is correct 
        # Initiate data collection from data miner 
        if should_collect_data(curr_user, curr_que): 
            if curr_que.is_multi_step: 
                collect_multi_step_data(curr_user) 
            else: 
                collect_final_data(curr_user, is_failure=False)
        
        # Check if it's final step already for multi-step problems 
        if curr_que.is_multi_step and step < curr_que.total_steps: 
            curr_user.end_mid = None 
            curr_user.save() 
            return HttpResponseRedirect(reverse(
                "questioner:modelling", args=[
                    question_type, question_id, os_user_id, 0, step + 1
                ]
            ))
        
        # Redirect to complete page 
        return HttpResponseRedirect(reverse(
            "questioner:complete", args=[
                curr_que.question_type, curr_que.question_id, curr_user.os_user_id
            ]
        ))
    else: # Submission failed 
        # Initiate failure attempt collection 
        if response[1] and should_collect_data(curr_user, curr_que): 
            collect_fail_data(curr_user)
        
        context={
            "user": curr_user, 
            "question": curr_que, 
            "model_comparison": response[0] # failure message 
        }
        if curr_que.is_multi_step:
            context["step"] = Question_Step_PS.objects.filter(
                question=curr_que
            ).get(step_number=step)
        
        return render(
            request, "questioner/modelling.html", 
            context=context
        )


def solution(request: HttpRequest, question_type: str, question_id: int, os_user_id: str, step=1): 
    """ 
    If a user gives up on the problem, some form of solution is presented.
    
    **Context:**  
    
    The reference model should be presented to the user in some forms (defined differently in each of the question model).
    
    - Reference model is automatically derived imported into user's working space for questions in part studios. 
    - Access to reference document is provided to all questions. 
    
    Corresponding instructions should also be shown to teach the user how to use the reference model to find mismatched geometries, if needed. 
    
    **Arguments:**
    
    - ``question_type``: one of the supported question type model inheriting :model:`questioner.Question`  
    - ``question_id``: the unique ID of the question 
    - ``os_user_id``: the unique ID linked to the user's :model:`questioner.AuthUser` profile 
    - ``step``: only applicable to multi-step questions (index starts from 1)
    
    **Template:** 
    
    :template:`questioner/solution.html` 
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    if question_type not in Q_Type_Dict.keys(): 
        return HttpResponseNotFound("Question type not found") 
    curr_que = get_object_or_404(Q_Type_Dict[question_type], question_id=question_id)

    # Reset user data model 
    curr_user.is_modelling = False 
    curr_user.save() 
    # Initiate any give-up actions if available 
    if curr_que.is_multi_step: 
        instructions, do_collect_data = curr_que.give_up(curr_user, step)
    else: 
        instructions, do_collect_data = curr_que.give_up(curr_user)
    # Record model's final state at the point of give-up 
    if do_collect_data and should_collect_data(curr_user, curr_que): 
        collect_final_data(curr_user, is_failure=True)

    return render(
        request, "questioner/solution.html", 
        context={
            "user": curr_user, 
            "question": curr_que, 
            "instructions": instructions
        }
    )


def complete(request: HttpRequest, question_type: str, question_id: int, os_user_id: str): 
    """ 
    The view that the users see when a question is finished. 
    
    **Context:** 
    
    It provides a brief summary of the user's performance and relative comparisons to all other users. 
    
    Users should be able to return to :view:`questioner.index` to start new question attempts. 
    
    **Arguments:**
    
    - ``question_type``: one of the supported question type model inheriting :model:`questioner.Question`  
    - ``question_id``: the unique ID of the question 
    - ``os_user_id``: the unique ID linked to the user's :model:`questioner.AuthUser` profile 
    
    **Template:** 
    
    :template:`questioner/complete.html`
    """
    curr_user = get_object_or_404(AuthUser, os_user_id=os_user_id)
    if question_type not in Q_Type_Dict.keys(): 
        return HttpResponseNotFound("Question type not found") 
    curr_que = get_object_or_404(Q_Type_Dict[question_type], question_id=question_id)

    if "best" in request.GET: 
        show_best = True 
    else: 
        show_best = False

    return render(
        request, "questioner/complete.html", 
        context={
            "user": curr_user, 
            "question": curr_que, 
            "show_best": show_best, 
            "stats_display": curr_que.show_result(curr_user, show_best=show_best)
        }
    )