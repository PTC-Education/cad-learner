from datetime import datetime

import django_rq
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from .models import HistoryData, HistoryData_PS, HistoryData_AS, HistoryData_MSPS
from questioner.models import AuthUser, QuestionType, Question_MSPS


# Create your views here.
D_Type_Dict = {
    QuestionType.SINGLE_PART_PS: HistoryData_PS, 
    QuestionType.MULTI_PART_PS: HistoryData_PS, 
    QuestionType.ASSEMBLY: HistoryData_AS
}


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