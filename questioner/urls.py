from django.urls import path 
from .import views

app_name = 'questioner'
urlpatterns = [
    path('oauthSignin/', views.login, name='login'), 
    path('oauthRedirect/', views.authorize, name='authorize'), 
    path('index/<str:os_user_id>/', views.index, name='index'), 
    path('modelling/<str:question_type>/<int:question_id>/<str:os_user_id>/<int:initiate>/', views.model, name='modelling'), 
    path('check/<str:question_type>/<int:question_id>/<str:os_user_id>/', views.check_model, name="check"), 
    path('give_up/<str:question_type>/<int:question_id>/<str:os_user_id>/', views.give_up, name="give_up"), 
    path('complete/<str:question_type>/<int:question_id>/<str:os_user_id>/', views.complete, name="complete")
]