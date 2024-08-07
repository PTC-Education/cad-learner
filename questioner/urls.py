from django.urls import path 
from .import views

app_name = 'questioner'
urlpatterns = [
    path('',views.home), 
    path('home/<str:os_user_id>/',views.home, name="home"),
    path('dashboard/<str:os_user_id>/',views.dashboard, name="dashboard"),
    path('certificate/<str:os_user_id>/<int:cert_id>/<str:cert_date>',views.certificate, name="certificate"),
    path('oauthSignin/', views.login, name='login'), 
    path('oauthRedirect/', views.authorize, name='authorize'), 
    path('index/<str:os_user_id>/', views.index, name='index'), 
    path('modelling/<str:question_type>/<int:question_id>/<str:os_user_id>/<int:initiate>/', views.model, name='modelling'), 
    path('modelling/<str:question_type>/<int:question_id>/<str:os_user_id>/<int:initiate>/<int:step>/', views.model, name='modelling'), 
    path('check/<str:question_type>/<int:question_id>/<str:os_user_id>/', views.check_model, name="check"), 
    path('check/<str:question_type>/<int:question_id>/<str:os_user_id>/<int:step>/', views.check_model, name="check"), 
    path('solution/<str:question_type>/<int:question_id>/<str:os_user_id>/', views.solution, name="solution"), 
    path('solution/<str:question_type>/<int:question_id>/<str:os_user_id>/<int:step>/', views.solution, name="solution"), 
    path('complete/<str:question_type>/<int:question_id>/<str:os_user_id>/', views.complete, name="complete")
]