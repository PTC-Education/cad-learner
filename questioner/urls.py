from django.urls import path 
from .import views

app_name = 'questioner'
urlpatterns = [
    path('',views.home), 
    path('<str:os_user_id>/',views.home, name="home"),
    path('oauthSignin/', views.login, name='login'), 
    path('oauthRedirect/', views.authorize, name='authorize'), 
    path('index/<str:os_user_id>/', views.index, name='index'), 
    path('modelling/<str:question_type>/<int:question_id>/<str:os_user_id>/<int:initiate>/', views.model, name='modelling'), 
    path('check/<str:question_type>/<int:question_id>/<str:os_user_id>/', views.check_model, name="check"), 
    path('solution/<str:question_type>/<int:question_id>/<str:os_user_id>/', views.solution, name="solution"), 
    path('complete/<str:question_type>/<int:question_id>/<str:os_user_id>/', views.complete, name="complete")
]