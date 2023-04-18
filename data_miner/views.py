import io 
import base64
from typing import List 
from datetime import datetime
import numpy as np 
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

import django_rq
from django.shortcuts import render 
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from .models import HistoryData, HistoryData_PS, HistoryData_AS, HistoryData_MSPS
from questioner.models import AuthUser, Question, QuestionType, Question_MSPS, ElementType


# Create your views here.
D_Type_Dict = {
    QuestionType.SINGLE_PART_PS: HistoryData_PS, 
    QuestionType.MULTI_PART_PS: HistoryData_PS, 
    QuestionType.ASSEMBLY: HistoryData_AS, 
    QuestionType.MULTI_STEP_PS: HistoryData_MSPS
}


######################## Data Presentation ########################
def convert_plot_to_str(plot) -> str: 
    """
    Given an input ``plot`` as a matplotlib.figure.Figure(), convert the resulting plot to a base64 encoded PNG image in string for HTML output 
    """
    img_output = io.BytesIO()
    FigureCanvasAgg(plot).print_png(img_output)
    img_output.seek(0)
    img_data = base64.b64encode(img_output.read())
    return "data:image/png;base64," + str(img_data)[2:-1]


def calc_feature_cnt(qid: int) -> List[int]: 
    """
    Given a ``question_id`` for a :model:`questioner.Question` object, return a list of the number of features used for all user attempts on the question 
    """
    que = Question.objects.get(question_id=qid)
    temp_cnt = [] 
    if que.question_type == QuestionType.MULTI_STEP_PS: 
        records = HistoryData_MSPS.objects.filter(
            question_id=qid, is_final_failure=False, time_of_completion__isnull=False
        )
        for entry in records: 
            temp_cnt.append(
                len(entry.step_feature_lists[-1]['features'])
            )
    elif que.allowed_etype == ElementType.PARTSTUDIO: 
        records = HistoryData_PS.objects.filter(
            question_id=qid, is_final_failure=False, time_of_completion__isnull=False
        )
        for entry in records: 
            temp_cnt.append(
                len(entry.final_feature_list['features'])
            )
    else: # que.allowed_etype == ElementType.ASSEMBLY 
        records = HistoryData_AS.objects.filter(
            question_id=qid, is_final_failure=False, time_of_completion__isnull=False
        )
        for entry in records: 
            temp_cnt.append(
                len(entry.final_assembly_def['rootAssembly']['features']) + 
                sum([len(subass['features']) for subass in entry.final_assembly_def['subAssemblies']])
            )
    return temp_cnt
    

def dashboard(request: HttpRequest): 
    """
    This view provides a dashboard of analytics to present some basic statistics of the collected user data 
    
    **Template:** 
    
    :template:`data_miner/dashboard.html`
    """
    context = {} 
    
    # Buttons for detailed views 
    all_ques = Question.objects.filter(is_published=True)
    context['all_questions'] = sorted(all_ques, key=lambda x:x.question_name)
    
    # Simple counting 
    context['attempt_total'] = len(HistoryData.objects.all())
    context['user_attempt_total'] = len(HistoryData.objects.values('os_user_id').distinct())
    context['user_login_total'] = len(AuthUser.objects.all())
    
    # Successful/Failed attempts counts of all questions 
    x = np.arange(len(context['all_questions']))
    y_succ = np.zeros(len(context['all_questions'])) 
    y_fail = np.zeros(len(context['all_questions'])) 
    for i, qid in enumerate([q.question_id for q in context['all_questions']]): 
        temp = HistoryData.objects.filter(question_id=qid)
        y_succ[i] = len(temp.filter(
            is_final_failure=False, time_of_completion__isnull=False
        ))
        y_fail[i] = len(temp) - y_succ[i]
    
    fig_cnt_bar = Figure(figsize=(8, 6)) 
    ax = fig_cnt_bar.add_subplot(1, 1, 1)
    p1 = ax.bar(x, y_succ)
    p2 = ax.bar(x, y_fail, bottom=y_succ)
    
    ax.set_xlabel("Question Name")
    ax.set_ylabel("Number of Attempts")
    ax.set_xticks(x)
    ax.set_xticklabels([
        q.question_name + "\n(" + q.get_question_type_display() + ")" 
        for q in context['all_questions']
    ], rotation=90)
    ax.legend((p1[0], p2[0]), ("Successful", "Failed"))
    fig_cnt_bar.tight_layout()
    context['succ_fail_cnt'] = convert_plot_to_str(fig_cnt_bar)
    
    # Time spent distributtion on all questions 
    y_time = []
    for i, qid in enumerate([q.question_id for q in context['all_questions']]): 
        temp = HistoryData.objects.filter(
            question_id=qid, is_final_failure=False, time_of_completion__isnull=False 
        )
        temp_times = [] 
        for entry in temp: 
            temp_times.append(
                (entry.time_of_completion - entry.start_time).total_seconds() / 60
            )
        y_time.append(temp_times)
    
    fig_time_dist = Figure(figsize=(8, 6)) 
    ax = fig_time_dist.add_subplot(1, 1, 1)
    ax.boxplot(y_time, positions=np.arange(len(y_time)))
    ax.set_xlabel("Question Name")
    ax.set_ylabel("Time Spent of Attempts (mins)")
    ax.set_xticks(np.arange(len(y_time)))
    ax.set_xticklabels([
        q.question_name + "\n(" + q.get_question_type_display() + ")" 
        for q in context['all_questions']
    ], rotation=90)
    fig_time_dist.tight_layout()
    context['time_spent'] = convert_plot_to_str(fig_time_dist)
    
    # Number of features used in all questions 
    y_cnt = [calc_feature_cnt(q.question_id) for q in context['all_questions']] 
    
    fea_use_dist = Figure(figsize=(8, 6)) 
    ax = fea_use_dist.add_subplot(1, 1, 1)
    ax.boxplot(y_cnt, positions=np.arange(len(y_cnt)))
    ax.set_xlabel("Question Name")
    ax.set_ylabel("Number of Features Used")
    ax.set_xticks(np.arange(len(y_cnt)))
    ax.set_xticklabels([
        q.question_name + "\n(" + q.get_question_type_display() + ")" 
        for q in context['all_questions']
    ], rotation=90)
    fea_use_dist.tight_layout()
    context['features_used'] = convert_plot_to_str(fea_use_dist)
    
    return render(request, "data_miner/dashboard.html", context=context)


def dashboard_question(request: HttpRequest, qid: int): 
    """
    This view presents a dashboard of analytics for a specific question 
    
    **Arguments:** 
    
    - ``qid``: the ``question_id`` for a :model:`questioner.Question` 
    
    **Template:** 
    
    :template:`data_miner/dashboard_q.html`
    """
    question = Question.objects.get(question_id=qid)
    q_records = D_Type_Dict[question.question_type].objects.filter(question_id=qid)
    
    context = {
        "question": question, 
        "attempt_total": len(q_records)
    }
    
    # General counts for the question 
    context['additional_counts'] = ""
    context['additional_plots'] = ""
    if question.question_type == QuestionType.MULTI_STEP_PS: 
        pass 
    else: 
        context['additional_counts'] += '''
        <div class="box">
            Successful Attempts with First Submission: &nbsp<b>{}</b>
        </div>
        <div class="box">
            Successful Attempts with ≥1 Submission: &nbsp<b>{}</b>
        </div>
        <div class="box">
            Failed Attempts with Give Up: &nbsp<b>{}</b>
        </div>
        <div class="box">
            Failed Attempts without Give Up: &nbsp<b>{}</b>
        </div>
        '''.format(
            len(q_records.filter(
                is_final_failure=False, time_of_completion__isnull=False, 
                first_failed_time__isnull=True
            )), 
            len(q_records.filter(
                is_final_failure=False, time_of_completion__isnull=False, 
                first_failed_time__isnull=False 
            )), 
            len(q_records.filter(
                is_final_failure=True, time_of_completion__isnull=False
            )), 
            len(q_records.filter(
                time_of_completion__isnull=True, first_failed_time__isnull=False 
            ))
        )
        
    # Time spent distribution of the question 
    y_time = []
    for entry in q_records.filter(
        is_final_failure=False, time_of_completion__isnull=False
    ): 
        y_time.append(
            (entry.time_of_completion - entry.start_time).total_seconds() / 60
        )
    
    time_dist = Figure(figsize=(8, 6)) 
    ax = time_dist.add_subplot(1, 1, 1)
    ax.hist(y_time)
    ax.set_xlabel("Time Spent on the Question (mins)")
    ax.set_ylabel("Number of Users")
    time_dist.tight_layout()
    context['time_spent'] = convert_plot_to_str(time_dist) 
    
    # Feature counts of the question 
    fea_cnt = calc_feature_cnt(qid)
    fea_dist = Figure(figsize=(8, 6))
    ax = fea_dist.add_subplot(1, 1, 1)
    ax.hist(fea_cnt)
    ax.set_xlabel("Number of Features Used in the Question")
    ax.set_ylabel("Number of Users")
    fea_dist.tight_layout()
    context['feature_cnt'] = convert_plot_to_str(fea_dist) 
    
    return render(request, "data_miner/dashboard_q.html", context=context)


######################## Data Collection ########################
def collect_fail_data(user: AuthUser) -> None: 
    """ 
    When this view is called, some data of the failed submission attempt of the user is recorded 
    
    The timing of the triggering of this process is set in the questioner app, under each question type model. The kinds of data that are recorded for different question types may also be different, set in the specific :model:`data_miner.HistoryData` model (either :model:`data_miner.HistoryData_PS` or :model:`data_miner.HistoryData_AS`)
    """
    # Start a new data entry 
    data_entry = D_Type_Dict[user.curr_question_type](
        os_user_id=user.os_user_id, 
        start_time=user.last_start, 
        question_id=user.curr_question_id, 
        question_type=user.curr_question_type, 
        num_attempt = len(HistoryData.objects.filter(
            os_user_id=user.os_user_id, question_id=user.curr_question_id 
        )) + 1
    )
    data_entry.first_failed_time = timezone.now() 
    data_entry.save() 

    # Initiate failure data recrod 
    query_info = (
        user.os_domain, user.did, user.start_mid, 
        user.end_mid, user.eid, user.etype
    )
    # Send data collection jobs to the RQ queue 
    django_rq.enqueue(data_entry.first_failure_record, args=[user, query_info])


def collect_final_data(user: AuthUser, is_failure: bool) -> None: 
    """ 
    Once a user submits the model and passes the evaluation check, data of the design process and the product will be collected. This function initiates the collection process 
    """    
    # Create data entry or find created data entry if exists 
    try: 
        data_entry = D_Type_Dict[user.curr_question_type].objects.filter(
            os_user_id=user.os_user_id
        ).get(
            start_time=user.last_start
        )
    except ObjectDoesNotExist: 
        data_entry = D_Type_Dict[user.curr_question_type](
            os_user_id=user.os_user_id, 
            start_time=user.last_start, 
            question_id=user.curr_question_id, 
            question_type=user.curr_question_type, 
            num_attempt = len(HistoryData.objects.filter(
                os_user_id=user.os_user_id, question_id=user.curr_question_id 
            )) + 1
        )

    q_name = user.curr_question_type + "_" + str(user.curr_question_id)

    # history_data: Tuple[completion_datetime, time_taken, ...]
    if not is_failure: 
        attempt_data = user.completed_history[q_name][-1] 
    else: 
        attempt_data = user.failure_history[q_name][-1] 
    data_entry.is_final_failure = is_failure
    data_entry.time_of_completion = datetime.fromisoformat(attempt_data[0])
    data_entry.save() 
    
    # Initiate final submission data record 
    query_info = (
        user.os_domain, user.did, user.start_mid, 
        user.end_mid, user.eid, user.etype
    )
    # Send data collection jobs to the RQ queue 
    django_rq.enqueue(data_entry.final_sub_record, args=[user, query_info])


def collect_multi_step_data(user: AuthUser) -> None: 
    """
    This function is used to collect user data after completion of every step of a multi-step question. 
    """
    # Create data entry or find created data entry if exists 
    if user.curr_step == 1: 
        data_entry = HistoryData_MSPS(
            os_user_id=user.os_user_id, 
            start_time=user.last_start, 
            question_id=user.curr_question_id, 
            question_type=user.curr_question_type, 
            num_attempt = len(HistoryData.objects.filter(
                os_user_id=user.os_user_id, question_id=user.curr_question_id 
            )) + 1
        )
        data_entry.save() 
    else: 
        data_entry = HistoryData_MSPS.objects.filter(
            os_user_id=user.os_user_id
        ).get(
            start_time=user.last_start
        ) 
    
    # Record step completion time 
    data_entry.step_completion_time.append(
        datetime.strftime(timezone.now(), '%Y-%m-%d %H:%M:%S')
    )
        
    # Freeze query information 
    query_info = (
        user.os_domain, user.did, user.start_mid, 
        user.end_mid, user.eid, user.etype
    )
    
    # Check if this is the final step completed 
    if user.curr_step == Question_MSPS.objects.get(
        question_id=user.curr_question_id
    ).total_steps: 
        data_entry.is_final_failure = False 
        q_name = user.curr_question_type + "_" + str(user.curr_question_id)
        data_entry.time_of_completion = datetime.fromisoformat(
            user.completed_history[q_name][-1][0]
        )
        data_entry.save() 
        django_rq.enqueue(data_entry.collect_data, args=[user, query_info, True])
    else: 
        django_rq.enqueue(data_entry.collect_data, args=[user, query_info])