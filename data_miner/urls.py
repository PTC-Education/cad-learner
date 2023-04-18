from django.urls import path 
from .import views

app_name = 'data_miner'
urlpatterns = [
    path('dashboard/<int:qid>/', views.dashboard_question, name="question_dashboard"), 
    path('dashboard/',views.dashboard, name="dashboard")
]