from django.urls import path 
from .import views

app_name = 'questioner'
urlpatterns = [
    path('oauthSignin/', views.login, name='login'), 
    path('oauthRedirect/', views.authorize, name='authorize'), 
    path('index/<str:os_user_id>/', views.index, name='index'), 
    path('modelling/<str:question_name>/<str:os_user_id>/', views.model, name='model'), 
    path('check/<str:question_name>/<str:os_user_id>/', views.check_model, name="check"), 
    path('complete/<str:question_name>/<str:os_user_id>/', views.complete, name="complete")
]