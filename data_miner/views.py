from datetime import datetime

from rq import Queue 
from worker import conn

from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from .models import HistoryData_PS
from questioner.models import AuthUser, QuestionType


# The RQ queue that processes all time-consuming data mining operations 
# in the background 
q = Queue(connection=conn)


# Create your views here.
D_Type_Dict = {
    QuestionType.SINGLE_PART_PS: HistoryData_PS, 
    QuestionType.MULTI_PART_PS: HistoryData_PS
}


def collect_fail_data(user: AuthUser) -> bool: 
    """ When this view is called, some data of the failed submission attempt 
    of the user is recorded. The timing of the triggering of this process 
    is set in the questioner app, under each question type model. The kinds 
    of data that are recorded for different question types may also be 
    different, set in the specific history_data class model. 
    """
    # Start a new data entry 
    data_entry = D_Type_Dict[user.curr_question_type](
        os_user_id=user.os_user_id, 
        start_time=user.last_start, 
        question_id=user.curr_question_id, 
        question_type=user.curr_question_type 
    )
    data_entry.save() 

    # Initiate failure data recrod 
    query_info = (
        user.os_domain, user.did, user.start_mid, 
        user.end_mid, user.eid, user.etype
    )

    if (
        user.curr_question_type == QuestionType.SINGLE_PART_PS or 
        user.curr_question_type == QuestionType.MULTI_PART_PS 
    ): 
        data_entry.first_failed_time = timezone.now() 
        data_entry.save() 
        # Send data collection jobs to the RQ queue 
        q.enqueue(data_entry.first_failure_record, args=[user, query_info])
    return True


def collect_final_data(user: AuthUser) -> bool: 
    """ Once a user submits the model and passes the evaluation check, 
    data of the design process and the product will be collected. This 
    function initiates the collection process. 
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
            question_type=user.curr_question_type 
        )

    completion_data = user.completed_history[
        user.curr_question_type + "_" + str(user.curr_question_id)
    ][-1] # Tuple[completion_datetime, time_taken, ...]

    data_entry.time_of_completion = datetime.fromisoformat(completion_data[0])
    data_entry.num_attempt = completion_data[1]
    data_entry.save() 
    
    # Initiate final submission data record 
    query_info = (
        user.os_domain, user.did, user.start_mid, 
        user.end_mid, user.eid, user.etype
    )

    if (
        user.curr_question_type == QuestionType.SINGLE_PART_PS or 
        user.curr_question_type == QuestionType.MULTI_PART_PS 
    ): 
        # Send data collection jobs to the RQ queue 
        q.enqueue(data_entry.final_sub_record, args=[user, query_info])
    return True
