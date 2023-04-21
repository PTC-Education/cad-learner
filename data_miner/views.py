import io 
import base64
from typing import List, Dict 
from datetime import datetime
import numpy as np 
import cv2 
from matplotlib.figure import Figure
import matplotlib.dates as mdates 
from matplotlib.backends.backend_agg import FigureCanvasAgg

import django_rq
from django.shortcuts import render
from django.http import HttpRequest
from django.utils import timezone
from django.db.models import QuerySet
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


def calc_time_spent(
    q_records: QuerySet[D_Type_Dict.values()], qid: int, all: bool, 
    is_final_failure=False, all_success=False, has_failed_attempts=False
) -> List[float]: 
    """
    Given a ``question_id`` for a :model:`questioner.Question` object, return a list of the time spent by all user attempts on the question in minutes 
    
    **Arguments:** 
    
    - ``all``: if True, time spent of all attempts are returned, and other trailing arguments are ignored 
    - ``is_final_failure``: True if filter by successful attempts only; False otherwise 
    - ``all_success``: True if filter by all successful attempts; False to consider ``has_failed_attempts`` 
    - ``has_failed_attempts``: if True, no failed submissions are recorded; i.e., got the question right at the first attempt (not available for multi-step questions)
    """
    if all: 
        temp_set = q_records.filter(
            time_of_completion__isnull=False
        )
    elif is_final_failure: 
        temp_set = q_records.filter(
            time_of_completion__isnull=False, is_final_failure=True
        )
    elif all_success: 
        temp_set = q_records.filter(
            time_of_completion__isnull=False, is_final_failure=False 
        )
    elif has_failed_attempts: 
        temp_set = q_records.filter(
            time_of_completion__isnull=False, is_final_failure=False, first_failed_time__isnull=False
        )
    else: 
        temp_set = q_records.filter(
            time_of_completion__isnull=False, is_final_failure=False, first_failed_time__isnull=True
        )
    all_times = [] 
    for entry in temp_set: 
        curr_time = (entry.time_of_completion - entry.start_time).total_seconds() 
        if curr_time <= 4000: 
            all_times.append(curr_time / 60) # in minutes 
    return all_times


def calc_feature_cnt(q_records: QuerySet[D_Type_Dict.values()], qid: int) -> List[int]: 
    """
    Given a ``question_id`` for a :model:`questioner.Question` object, return a list of the number of features used for all user attempts on the question 
    """
    que = Question.objects.get(question_id=qid)
    temp_cnt = [] 
    if que.question_type == QuestionType.MULTI_STEP_PS: 
        records = q_records.filter(
            is_final_failure=False, time_of_completion__isnull=False
        )
        for entry in records: 
            temp_cnt.append(
                len(entry.step_feature_lists[-1]['features'])
            )
    elif que.allowed_etype == ElementType.PARTSTUDIO: 
        records = q_records.filter(
            is_final_failure=False, time_of_completion__isnull=False
        )
        for entry in records: 
            temp_cnt.append(
                len(entry.final_feature_list['features'])
            )
    else: # que.allowed_etype == ElementType.ASSEMBLY 
        records = q_records.filter(
            is_final_failure=False, time_of_completion__isnull=False
        )
        for entry in records: 
            temp_cnt.append(
                len(entry.final_assembly_def['rootAssembly']['features']) + 
                sum([len(subass['features']) for subass in entry.final_assembly_def['subAssemblies']])
            )
    return temp_cnt
    

def shaded_view_cluster(
    q_records: QuerySet[D_Type_Dict.values()], qid: int, select_img="FRT"
) -> str: 
    """
    Given a ``question_id`` for a :model:`questioner.Question` object, this function analyze all the captured shaded view images of the final workspace. This function automatically clusters all the images based on the similarity (MSE difference) between images. 
    
    A formatted table presenting the clustering results is returned. 
    
    ``select_img``: ``"FRT"`` or ``"BLB"`` 
    """
    def image_error(img1, img2):
        """ Calculate the mean squared error (MSE) between two images """
        def readb64_img(uri):
            """ Clean the raw image from html format """
            encoded_data = uri.split(',')[1]
            nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return img
    
        # load the input images
        img1 = readb64_img(img1)
        img2 = readb64_img(img2)
        # convert the images to grayscale
        img1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        img2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
        # Compute MSE between two images
        h, w = img1.shape
        diff = cv2.subtract(img1, img2)
        err = np.sum(diff**2)
        mse = err/(float(h*w))
        return mse, diff
        
    # Get all images for the question 
    imgs = [] 
    q_type = Question.objects.get(question_id=qid).question_type
    for entry in q_records: 
        if q_type == QuestionType.MULTI_STEP_PS: 
            if len(entry.step_shaded_views) == Question_MSPS.objects.get(question_id=qid).total_steps: 
                imgs.append(entry.step_shaded_views[-1][select_img])
        else: 
            if entry.final_shaded_views: 
                imgs.append(entry.final_shaded_views[select_img])
    # Calculate MSE between images 
    err_mat = np.identity(len(imgs))
    for i in range(len(imgs)): 
        for j in range(i + 1, len(imgs)): 
            err_mat[i][j] = image_error(imgs[i], imgs[j])[0]
    # Cluster images based on MSE values 
    imgs_ind = list(range(len(imgs))) 
    clusters = [] 
    while imgs_ind: 
        curr_ind = imgs_ind.pop(0)
        clusters.append([curr_ind])
        curr_cluster_size = len(clusters)
        for item in imgs_ind.copy(): 
            if err_mat[curr_ind][item] <= 10: 
                imgs_ind.remove(item)
                clusters[curr_cluster_size-1].append(item)
    clusters.sort(key=lambda x:len(x), reverse=True)
    # Format results to be returned 
    result = '''
    <table>
        <tr>
            <th>View No.</th>
            <th>Isometric View of the Final Model</th>
            <th>Number of Attempts with the Same View</th>
        </tr>
    '''
    for i, cluster in enumerate(clusters): 
        # if len(cluster) == 1: 
        #     result += f'''
        #     <tr>
        #         <td>{i+1}</td>
        #         <td>Others</td>
        #         <td>{len(clusters) - i}</td>
        #     </tr>
        #     '''
        #     break 
        result += f'''
        <tr>
            <td>{i+1}</td>
            <td><img src="{imgs[cluster[0]]}" alt=""/></td>
            <td>{len(cluster)}</td>
        </tr>
        '''
    return result + "</table>"


def get_feature_counts(
    q_records: QuerySet[D_Type_Dict.values()], qid: int
) -> Dict[str, int]: 
    """
    Given a ``question_id`` for a :model:`questioner.Question` object, return a dictionary of the features used and the average counts of features used per user attempt on the question 
    """
    feature_cnts = {} 
    que = Question.objects.get(question_id=qid)
    if que.question_type == QuestionType.MULTI_STEP_PS: 
        total_steps = Question_MSPS.objects.get(question_id=qid).total_steps
        for entry in q_records: 
            if len(entry.step_feature_lists) == total_steps: 
                for fea in entry.step_feature_lists[-1]['features']: 
                    if fea['featureType'] not in feature_cnts: 
                        feature_cnts[fea['featureType']] = 0 
                    feature_cnts[fea['featureType']] += 1 
    elif que.allowed_etype == ElementType.PARTSTUDIO: 
        for entry in q_records: 
            if entry.final_feature_list: 
                for fea in entry.final_feature_list['features']: 
                    if fea['featureType'] not in feature_cnts: 
                        feature_cnts[fea['featureType']] = 0 
                    feature_cnts[fea['featureType']] += 1 
    else: # Assembly 
        for entry in q_records: 
            if entry.final_assembly_def: 
                for fea in entry.final_assembly_def['rootAssembly']['features']: 
                    if fea['featureData']['mateType'] not in feature_cnts: 
                        feature_cnts[fea['featureData']['mateType']] = 0 
                    feature_cnts[fea['featureData']['mateType']] += 1 
                for subass in entry.final_assembly_def['subAssemblies']: 
                    for fea in subass['features']: 
                        if fea['featureData']['mateType'] not in feature_cnts: 
                            feature_cnts[fea['featureData']['mateType']] = 0 
                        feature_cnts[fea['featureData']['mateType']] += 1 
    
    num_attempts = len(q_records)
    for key, item in feature_cnts.items(): 
        feature_cnts[key] = round(item / num_attempts, 1)
    return feature_cnts 


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
    all_records = HistoryData.objects.all() 
    context['attempt_total'] = len(all_records)
    context['user_attempt_total'] = len(all_records.values('os_user_id').distinct())
    context['user_login_total'] = len(AuthUser.objects.all())
    
    # Cumulative number of question attempts 
    temp = sorted(all_records, key=lambda x:x.start_time)
    cum_cnt_plot = Figure(figsize=(8, 6))
    ax = cum_cnt_plot.add_subplot(1, 1, 1)
    ax.plot([e.start_time for e in temp], [i + 1 for i in range(len(temp))])
    for label in ax.get_xticklabels():
        label.set(rotation=90)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative Number of Question Attempts")
    cum_cnt_plot.tight_layout() 
    context['cum_attempt_cnt'] = convert_plot_to_str(cum_cnt_plot)
    
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
    y_time = [
        calc_time_spent(
            D_Type_Dict[q.question_type].objects.filter(question_id=q.question_id), 
            q.question_id, all=True
        ) 
        for q in context['all_questions']
    ]
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
    y_cnt = [
        calc_feature_cnt(
            D_Type_Dict[q.question_type].objects.filter(question_id=q.question_id), 
            q.question_id
        ) 
        for q in context['all_questions']
    ] 
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
    if question.question_type == QuestionType.MULTI_STEP_PS: 
        total_steps = Question_MSPS.objects.get(question_id=qid).total_steps
        context['additional_counts'] += '''
        <div class="box">
            Successful Full Attempts (completed last step): &nbsp<b>{}</b>
        </div>
        <div class="box">
            Successful Partial Attempts (before reaching last step): &nbsp<b>{}</b>
        </div>
        '''.format(
            sum([
                1 if len(entry.step_completion_time) == total_steps else 0 
                for entry in q_records
            ]), 
            sum([
                1 if entry.step_completion_time and len(entry.step_completion_time) < total_steps else 0 
                for entry in q_records
            ])
        )
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
    
    context['additional_plots'] = ""
    # Cumulative number of question attempts 
    temp = sorted(q_records, key=lambda x:x.start_time)
    cum_cnt_plot = Figure(figsize=(6, 4))
    ax = cum_cnt_plot.add_subplot(1, 1, 1)
    ax.plot([e.start_time for e in temp], [i + 1 for i in range(len(temp))])
    for label in ax.get_xticklabels():
        label.set(rotation=90)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative Number of Question Attempts")
    cum_cnt_plot.tight_layout() 
    context['cum_attempt_cnt'] = convert_plot_to_str(cum_cnt_plot)
    
    # Time spent distribution of the question 
    y_time = calc_time_spent(q_records, qid, all=True)
    time_dist = Figure(figsize=(6, 4)) 
    ax = time_dist.add_subplot(1, 1, 1)
    ax.hist(y_time)
    ax.set_xlabel("Time Spent on the Question (mins)")
    ax.set_ylabel("Number of Users")
    time_dist.tight_layout()
    context['time_spent'] = convert_plot_to_str(time_dist) 
    
    # Time spent comparison of different outcomes of the question 
    if question.question_type == QuestionType.MULTI_STEP_PS: 
        total_steps = Question_MSPS.objects.get(question_id=qid).total_steps
        records = HistoryData_MSPS.objects.filter(step_completion_time__isnull=False)
        step_time = [[] for _ in range(total_steps)]
        for entry in records: 
            for i, t in enumerate(entry.step_completion_time): 
                if i == 0: 
                    step_time[i].append(
                        (datetime.fromisoformat(t) - entry.start_time.replace(tzinfo=None)).total_seconds() / 60
                    )
                else: 
                    step_time[i].append(
                        (datetime.fromisoformat(t) - datetime.fromisoformat(
                            entry.step_completion_time[i-1]
                        )).total_seconds() / 60 
                    )
                    
        fig_time_compare = Figure(figsize=(6, 4))
        ax = fig_time_compare.add_subplot(1, 1, 1)
        ax.boxplot(step_time, positions=np.arange(len(step_time)))
        ax.set_xlabel("Step Number of the Question")
        ax.set_ylabel("Time Spent on Steps (mins)")
        ax.set_xticks(np.arange(len(step_time)))
        ax.set_xticklabels([f"Step {i+1}" for i in range(len(step_time))])
        fig_time_compare.tight_layout()
        context['time_spent_comparison'] = convert_plot_to_str(fig_time_compare)
    else: 
        direct_succ = calc_time_spent(
            q_records, qid, all=False, is_final_failure=False, has_failed_attempts=False
        )
        indirect_succ = calc_time_spent(
            q_records, qid, all=False, is_final_failure=False, has_failed_attempts=True
        )
        failure = calc_time_spent(q_records, qid, all=False, is_final_failure=True)
        
        fig_time_compare = Figure(figsize=(6, 4))
        ax = fig_time_compare.add_subplot(1, 1, 1)
        ax.boxplot([direct_succ, indirect_succ, failure], positions=np.arange(3))
        ax.set_xlabel("Question Completion Result")
        ax.set_ylabel("Time Spent of Challenge (mins)")
        ax.set_xticks(np.arange(3))
        ax.set_xticklabels([
            "Success without\nfailed attempts", 
            "Success with ≥1\nfailed attempts", 
            "Failure with give-up"
        ])
        fig_time_compare.tight_layout()
        context['time_spent_comparison'] = convert_plot_to_str(fig_time_compare)
    
    # Feature counts of the question 
    fea_cnt = calc_feature_cnt(q_records, qid)
    fea_dist = Figure(figsize=(6, 4))
    ax = fea_dist.add_subplot(1, 1, 1)
    ax.hist(fea_cnt)
    ax.set_xlabel("Number of Features Used in the Question")
    ax.set_ylabel("Number of Users")
    fea_dist.tight_layout()
    context['feature_cnt'] = convert_plot_to_str(fea_dist) 
    
    # Cluster final screen capture of the workspace 
    if Question.objects.get(question_id=qid).allowed_etype == ElementType.PARTSTUDIO: 
        if len(HistoryData.objects.filter(question_id=qid)) >= 5: 
            context['additional_plots'] += shaded_view_cluster(q_records, qid)
            
    # Average count of features used per user in the question 
    if len(HistoryData.objects.filter(question_id=qid)) >= 1: 
        fea_cnts = get_feature_counts(q_records, qid)
        fea_cnt_table = '''
        <table>
            <tr>
                <th>Feature Type</th>
                <th>Avg. Num. of Feature Used per Attempt</th>
            </tr>
        '''
        for key, item in sorted(fea_cnts.items(), key=lambda x:x[1], reverse=True): 
            fea_cnt_table += f'''
            <tr>
                <td>{key}</td>
                <td>{item}</td>
            </tr>
            '''
        context['additional_plots'] += "<br /><br />" + fea_cnt_table + "</table>"
    
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