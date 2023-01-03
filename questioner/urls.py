from django.urls import path 
from .import views

app_name = 'questioner'
urlpatterns = [
    path('oauthSignin/', views.login, name='login'), 
    path('oauthRedirect/', views.authorize, name='authorize'), 
    path('index/<str:os_user_id>/', views.index, name='index'), 
    path('modelling/<int:question_id>/<str:os_user_id>/', views.model, name='modelling'), 
    path('check/<int:question_id>/<str:os_user_id>/', views.check_model, name="check"), 
    path('complete/<int:question_id>/<str:os_user_id>/', views.complete, name="complete")
]