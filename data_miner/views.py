import io 
import base64
from typing import List, Dict, Union 
from datetime import datetime
import numpy as np 
from PIL import Image
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import requests
import json

import django_rq
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.db import connection
from django.db.models import QuerySet, Func, Value, JSONField, IntegerField
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

# A queryset of any of the per-type history models in ``D_Type_Dict``
HistoryQuerySet = QuerySet[Union[HistoryData_PS, HistoryData_AS, HistoryData_MSPS]]


# Max mean squared error (grayscale, 0-255) for two shaded views to count as the
# same model. Calibrated on prod data (2026-11): identical-looking models score
# ~100-500 from 1px framing/anti-aliasing shifts; genuinely different models
# (wrong thickness, flipped part) score 3000+.
SHADED_VIEW_MSE_THRESHOLD = 1000


class JsonbPathQueryArray(Func):
    """ Postgres ``jsonb_path_query_array(json, path)`` """
    function = 'jsonb_path_query_array'
    template = '%(function)s(%(expressions)s::jsonpath)'
    output_field = JSONField()


class JsonbArrayLength(Func):
    """ Postgres ``jsonb_array_length(json)`` """
    function = 'jsonb_array_length'
    output_field = IntegerField()


def iter_feature_types(records: QuerySet, que: Question):
    """
    For a part studio (single-/multi-part or multi-step) question ``que``, yield ``(step_count, feature_types)`` for each record in ``records`` with a non-empty feature list. ``feature_types`` lists the ``featureType`` of every feature in the final feature list (the last step's list for multi-step questions); ``step_count`` is the number of completed steps for multi-step questions and None otherwise.

    The feature lists are very large JSON documents (over 1 GB in total), so on Postgres only the feature types are extracted in the database. Other backends (e.g., local SQLite) stream the full column and extract them in Python.
    """
    is_msps = que.question_type == QuestionType.MULTI_STEP_PS
    col = 'step_feature_lists' if is_msps else 'final_feature_list'

    if connection.vendor == 'postgresql':
        if is_msps:
            rows = records.annotate(
                _present=JsonbArrayLength(col),
                _types=JsonbPathQueryArray(col, Value('$[last].features[*].featureType'))
            )
        else:
            rows = records.annotate(
                # [] when the feature list is empty ({}), so the record is skipped
                _present=JsonbPathQueryArray(col, Value('$.features.size()')),
                _types=JsonbPathQueryArray(col, Value('$.features[*].featureType'))
            )
        for present, types in rows.values_list('_present', '_types').iterator(chunk_size=200):
            if present:
                yield (present if is_msps else None), types
    else:
        for fea_list in records.values_list(col, flat=True).iterator(chunk_size=50):
            if fea_list:
                if is_msps:
                    yield len(fea_list), [fea['featureType'] for fea in fea_list[-1]['features']]
                else:
                    yield None, [fea['featureType'] for fea in fea_list['features']]


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
    q_records: HistoryQuerySet, qid: int, all: bool, 
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
        temp_set = q_records.filter(is_final_failure=False)
    elif has_failed_attempts: 
        temp_set = q_records.filter(
            is_final_failure=False, first_failed_time__isnull=False
        )
    else: 
        temp_set = q_records.filter(
            is_final_failure=False, first_failed_time__isnull=True
        )
    all_times = []
    # Only fetch the two timestamps; full rows carry very large JSON columns
    for start_time, time_of_completion in temp_set.values_list(
        'start_time', 'time_of_completion'
    ).iterator():
        if time_of_completion is None:
            continue
        curr_time = (time_of_completion - start_time).total_seconds()
        if curr_time <= 4000:
            all_times.append(curr_time / 60) # in minutes
    return all_times


def calc_feature_cnt(q_records: HistoryQuerySet, qid: int) -> List[int]: 
    """
    Given a ``question_id`` for a :model:`questioner.Question` object, return a list of the number of features used for all user attempts on the question 
    """
    que = Question.objects.get(question_id=qid)
    temp_cnt = []
    records = q_records.filter(is_final_failure=False)
    if que.question_type == QuestionType.MULTI_STEP_PS or que.allowed_etype == ElementType.PARTSTUDIO:
        for _, fea_types in iter_feature_types(records, que):
            temp_cnt.append(len(fea_types))
    else: # que.allowed_etype == ElementType.ASSEMBLY
        # Assembly definitions are small; fetch just this column, streamed in chunks
        for final_assembly_def in records.values_list(
            'final_assembly_def', flat=True
        ).iterator(chunk_size=50):
            if final_assembly_def:
                temp_cnt.append(
                    len(final_assembly_def['rootAssembly']['features']) +
                    sum([len(subass['features']) for subass in final_assembly_def['subAssemblies']])
                )
    return temp_cnt
    

def shaded_view_cluster(
    q_records: HistoryQuerySet, qid: int, select_img="FRT"
) -> str: 
    """
    Given a ``question_id`` for a :model:`questioner.Question` object, this function analyze all the captured shaded view images of the final workspace. This function automatically clusters all the images based on the similarity (MSE difference) between images. 
    
    A formatted table presenting the clustering results is returned. 
    
    ``select_img``: ``"FRT"`` or ``"BLB"`` 
    """
    def readb64_img(uri: str):
        """ Clean the raw image from html format """
        encoded_data = uri.split(',')[1]
        base64_decoded = base64.b64decode(encoded_data)
        image = Image.open(io.BytesIO(base64_decoded))
        image = image.convert("L") # convert the images to grayscale
        return np.array(image)

    def image_error(img1, img2) -> float:
        """ Calculate the mean squared error (MSE) between two decoded images """
        diff = img1 - img2
        return float(np.mean(diff * diff, dtype=np.float64))

    # Get all images for the question, fetching only the shaded-view column
    imgs = []
    q_type = Question.objects.get(question_id=qid).question_type
    if q_type == QuestionType.MULTI_STEP_PS:
        total_steps = Question_MSPS.objects.get(question_id=qid).total_steps
        for step_shaded_views in q_records.values_list(
            'step_shaded_views', flat=True
        ).iterator(chunk_size=50):
            if len(step_shaded_views) == total_steps:
                imgs.append(step_shaded_views[-1][select_img])
    else:
        for final_shaded_views in q_records.values_list(
            'final_shaded_views', flat=True
        ).iterator(chunk_size=50):
            if final_shaded_views:
                imgs.append(final_shaded_views[select_img])
    # Decode each image once. Use a signed float type: subtracting the raw
    # uint8 pixels wraps around (e.g. 10 - 20 = 246), which corrupted the MSE
    decoded = [readb64_img(img).astype(np.float32) for img in imgs]
    # Cluster images based on MSE values. Greedy: each cluster seed is only
    # compared against the images not yet clustered, so the full n x n
    # error matrix is never needed.
    imgs_ind = list(range(len(imgs)))
    clusters = []
    while imgs_ind:
        curr_ind = imgs_ind.pop(0)
        clusters.append([curr_ind])
        curr_cluster_size = len(clusters)
        for item in imgs_ind.copy():
            if image_error(decoded[curr_ind], decoded[item]) <= SHADED_VIEW_MSE_THRESHOLD:
                imgs_ind.remove(item)
                clusters[curr_cluster_size-1].append(item)
    clusters.sort(key=lambda x:len(x), reverse=True)
    # Format results to be returned 
    result = '''
    <table>
        <tr>
            <th>View No.</th>
            <th>Isometric View of the Final Model</th>
            <th>Number of Successful Attempts with the Same View</th>
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
    q_records: HistoryQuerySet, qid: int
) -> Dict[str, int]: 
    """
    Given a ``question_id`` for a :model:`questioner.Question` object, return a dictionary of the features used and the average counts of features used per user attempt on the question 
    """
    feature_cnts = {} 
    que = Question.objects.get(question_id=qid)
    if que.question_type == QuestionType.MULTI_STEP_PS:
        total_steps = Question_MSPS.objects.get(question_id=qid).total_steps
        for step_cnt, fea_types in iter_feature_types(q_records, que):
            if step_cnt == total_steps:
                for fea_type in fea_types:
                    if fea_type not in feature_cnts:
                        feature_cnts[fea_type] = 0
                    feature_cnts[fea_type] += 1
    elif que.allowed_etype == ElementType.PARTSTUDIO:
        for _, fea_types in iter_feature_types(q_records, que):
            for fea_type in fea_types:
                if fea_type not in feature_cnts:
                    feature_cnts[fea_type] = 0
                feature_cnts[fea_type] += 1
    else: # Assembly
        for final_assembly_def in q_records.values_list(
            'final_assembly_def', flat=True
        ).iterator(chunk_size=50):
            if final_assembly_def:
                for fea in final_assembly_def['rootAssembly']['features']:
                    if fea['featureType'] != 'mate': 
                        fea_type = fea['featureType']
                    else: 
                        fea_type = fea['featureData']['mateType']
                    if fea_type not in feature_cnts: 
                        feature_cnts[fea_type] = 0 
                    feature_cnts[fea_type] += 1 
                for subass in final_assembly_def['subAssemblies']:
                    for fea in subass['features']: 
                        if fea['featureType'] != 'mate': 
                            fea_type = fea['featureType']
                        else: 
                            fea_type = fea['featureData']['mateType']
                        if fea_type not in feature_cnts: 
                            feature_cnts[fea_type] = 0 
                        feature_cnts[fea_type] += 1 
    
    num_attempts = q_records.count()
    for key, item in feature_cnts.items(): 
        feature_cnts[key] = round(item / num_attempts, 2)
    return feature_cnts 


def dashboard(request: HttpRequest): 
    """
    This view provides a dashboard of analytics to present some basic statistics of the collected user data 
    
    **Template:** 
    
    :template:`data_miner/dashboard.html`
    """
    context = {} 
    
    # Buttons for detailed views 
    all_ques = Question.objects.defer("drawing_jpeg").filter(is_published=True)
    context['all_questions'] = sorted(all_ques, key=lambda x:x.question_name)
    
    # Simple counting 
    all_records = HistoryData.objects.all() 
    context['all_records'] = all_records
    context['attempt_total'] = all_records.count()
    context['user_attempt_total'] = all_records.values('os_user_id').distinct().count()
    context['user_login_total'] = AuthUser.objects.count()
    
    return render(request, "data_miner/dashboard.html", context=context)

def cumulative_question_attempts(request: HttpRequest):
    """
    This AJAX view for creating a cumulative attempt plot
    """
    context = {} 

    temp = list(
        HistoryData.objects.order_by('start_time').values_list('start_time', flat=True)
    )
    cum_cnt_plot = Figure(figsize=(10, 6))
    ax = cum_cnt_plot.add_subplot(1, 1, 1)
    ax.plot(temp, [i + 1 for i in range(len(temp))])
    for label in ax.get_xticklabels():
        label.set(rotation=90)
    ax.set_xlabel("Date")
    ax.set_ylabel("Cumulative Number of Question Attempts")
    cum_cnt_plot.tight_layout() 
    context['cum_attempt_cnt'] = convert_plot_to_str(cum_cnt_plot)

    return HttpResponse(
        json.dumps(context),
        content_type="application/json"
    )

def succ_fail_cnt(request: HttpRequest):
    """
    This view provides a dashboard of analytics to present some basic statistics of the collected user data 
    
    **Template:** 
    
    :template:`data_miner/dashboard.html`
    """
    context = {} 

    all_ques = Question.objects.defer("drawing_jpeg").filter(is_published=True)
    all_ques = sorted(all_ques, key=lambda x:x.question_name)

    x = np.arange(len(all_ques))
    y_succ = np.zeros(len(all_ques)) 
    y_fail = np.zeros(len(all_ques)) 
    for i, qid in enumerate([q.question_id for q in all_ques]): 
        temp = HistoryData.objects.filter(question_id=qid)
        y_succ[i] = temp.filter(is_final_failure=False).count()
        y_fail[i] = temp.count() - y_succ[i]
    
    fig_cnt_bar = Figure(figsize=(10, 6)) 
    ax = fig_cnt_bar.add_subplot(1, 1, 1)
    p1 = ax.bar(x, y_succ)
    p2 = ax.bar(x, y_fail, bottom=y_succ)
    
    ax.set_xlabel("Question Name")
    ax.set_ylabel("Number of Attempts")
    ax.set_xticks(x)
    ax.set_xticklabels([
        q.question_name + " (" + q.question_type + ")" 
        for q in all_ques
    ], rotation=90)
    ax.legend((p1[0], p2[0]), ("Successful", "Failed"))
    fig_cnt_bar.tight_layout()
    context['succ_fail_cnt'] = convert_plot_to_str(fig_cnt_bar)

    return HttpResponse(
        json.dumps(context),
        content_type="application/json"
    )

def time_distribution(request: HttpRequest):
    """
    This view provides a dashboard of analytics to present some basic statistics of the collected user data 
    
    **Template:** 
    
    :template:`data_miner/dashboard.html`
    """
    context = {} 

    all_ques = Question.objects.defer("drawing_jpeg").filter(is_published=True)
    all_ques = sorted(all_ques, key=lambda x:x.question_name)

    y_time = [
        calc_time_spent(
            D_Type_Dict[q.question_type].objects.filter(
                question_id=q.question_id, is_final_failure=False
            ), 
            q.question_id, all=True
        ) 
        for q in all_ques
    ]
    fig_time_dist = Figure(figsize=(10, 6)) 
    ax = fig_time_dist.add_subplot(1, 1, 1)
    ax.boxplot(y_time, positions=np.arange(len(y_time)))
    ax.set_xlabel("Question Name")
    ax.set_ylabel("Time Spent of Successful Attempts (mins)")
    ax.set_xticks(np.arange(len(y_time)))
    ax.set_xticklabels([
        q.question_name + " (" + q.question_type + ")" 
        for q in all_ques
    ], rotation=90)
    fig_time_dist.tight_layout()
    context['time_distribution'] = convert_plot_to_str(fig_time_dist)

    return HttpResponse(
        json.dumps(context),
        content_type="application/json"
    )

def feature_count(request: HttpRequest):
    """
    This view provides a dashboard of analytics to present some basic statistics of the collected user data 
    
    **Template:** 
    
    :template:`data_miner/dashboard.html`
    """
    context = {} 

    all_ques = Question.objects.defer("drawing_jpeg").filter(is_published=True)
    all_ques = sorted(all_ques, key=lambda x:x.question_name)

    y_cnt = [
        calc_feature_cnt(
            D_Type_Dict[q.question_type].objects.filter(
                question_id=q.question_id, is_final_failure=False 
            ), 
            q.question_id
        ) 
        for q in all_ques
    ] 
    fea_use_dist = Figure(figsize=(10, 6)) 
    ax = fea_use_dist.add_subplot(1, 1, 1)
    ax.boxplot(y_cnt, positions=np.arange(len(y_cnt)))
    ax.set_xlabel("Question Name")
    ax.set_ylabel("Number of Features Used in Successful Attempts")
    ax.set_xticks(np.arange(len(y_cnt)))
    ax.set_xticklabels([
        q.question_name + " (" + q.question_type + ")" 
        for q in all_ques
    ], rotation=90)
    fea_use_dist.tight_layout()
    context['feature_count'] = convert_plot_to_str(fea_use_dist)

    return HttpResponse(
        json.dumps(context),
        content_type="application/json"
    )

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
        "attempt_total": q_records.count()
    }

    # General counts for the question
    context['additional_counts'] = ""
    if question.question_type == QuestionType.MULTI_STEP_PS:
        total_steps = Question_MSPS.objects.get(question_id=qid).total_steps
        step_completion_times = list(
            q_records.values_list('step_completion_time', flat=True)
        )
        context['additional_counts'] += '''
        <div class="box">
            Successful Full Attempts (completed last step): &nbsp<b>{}</b>
        </div>
        <div class="box">
            Successful Partial Attempts (before reaching last step): &nbsp<b>{}</b>
        </div>
        '''.format(
            sum([
                1 if len(sct) == total_steps else 0
                for sct in step_completion_times
            ]),
            sum([
                1 if sct and len(sct) < total_steps else 0
                for sct in step_completion_times
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
            q_records.filter(
                is_final_failure=False, first_failed_time__isnull=True
            ).count(),
            q_records.filter(
                is_final_failure=False, first_failed_time__isnull=False
            ).count(),
            q_records.filter(
                is_final_failure=True, time_of_completion__isnull=False
            ).count(),
            q_records.filter(
                time_of_completion__isnull=True, first_failed_time__isnull=False
            ).count()
        )

    context['additional_plots'] = ""
    # Cumulative number of question attempts
    temp = list(
        q_records.order_by('start_time').values_list('start_time', flat=True)
    )
    cum_cnt_plot = Figure(figsize=(6, 4))
    ax = cum_cnt_plot.add_subplot(1, 1, 1)
    ax.plot(temp, [i + 1 for i in range(len(temp))])
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
        # Only this question's records (previously every MSPS question's
        # records were loaded, which could also overflow ``step_time``)
        records = q_records.filter(
            step_completion_time__isnull=False
        ).values_list('start_time', 'step_completion_time')
        step_time = [[] for _ in range(total_steps)]
        for start_time, step_completion_time in records:
            for i, t in enumerate(step_completion_time[:total_steps]):
                if i == 0:
                    step_time[i].append(
                        (datetime.fromisoformat(t) - start_time.replace(tzinfo=None)).total_seconds() / 60
                    )
                else:
                    step_time[i].append(
                        (datetime.fromisoformat(t) - datetime.fromisoformat(
                            step_completion_time[i-1]
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
    fea_cnt = calc_feature_cnt(
        q_records.filter(is_final_failure=False), qid
    )
    fea_dist = Figure(figsize=(6, 4))
    ax = fea_dist.add_subplot(1, 1, 1)
    ax.hist(fea_cnt)
    ax.set_xlabel("Number of Features Used in Successful Attempts")
    ax.set_ylabel("Number of Users")
    fea_dist.tight_layout()
    context['feature_cnt'] = convert_plot_to_str(fea_dist) 
    
    # Cluster final screen capture of the workspace 
    history_cnt = HistoryData.objects.filter(question_id=qid).count()
    if question.allowed_etype == ElementType.PARTSTUDIO:
        if history_cnt >= 1:
            context['additional_plots'] += shaded_view_cluster(
                q_records.filter(is_final_failure=False), qid
            )

    # Average count of features used per user in the question
    if history_cnt >= 5:
        fea_cnts = get_feature_counts(q_records, qid)
        fea_cnt_table = '''
        <table>
            <tr>
                <th>Feature Type</th>
                <th>Avg. Num. of Feature Used per Succ. Attempt</th>
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