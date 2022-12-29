from django.urls import path 
from .import views

app_name = 'data_miner'
urlpatterns = [
    path('collect/<str:os_user_id>/', views.collect_data, name='collect_data')
]