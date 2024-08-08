from django.urls import path 
from .import views

app_name = 'data_miner'
urlpatterns = [
    path('dashboard/q/<int:qid>/', views.dashboard_question, name="question_dashboard"), 
    path('dashboard/', views.dashboard, name="dashboard"),
    path('cumulative_question_attempts/', views.cumulative_question_attempts, name="cumulative_question_attempts"),
    path('succ_fail_cnt/', views.succ_fail_cnt, name="succ_fail_cnt"),
    path('time_distribution', views.time_distribution, name="time_distribution"),
    path('feature_count', views.feature_count, name="feature_count")
]