from typing import Any
from django.contrib import admin
from django.http import HttpRequest
from django.db.models import QuerySet
from .models import Question


# Register your models here.
class QuestionsAdmin(admin.ModelAdmin): 
    list_display = [
        'question_name', 'difficulty', 'completion_count', 'published'
    ]
    readonly_fields = [
        'thumbnail', 'model_mass', 'model_volume', 'model_SA', 'model_COM_x', 
        'model_COM_y', 'model_COM_z', 'published'
    ]
    search_fields = ['question_name', 'cad_drawing']
    actions = ['publish_question', 'update_model']

    @admin.action(description="Publish/Hide questions")
    def publish_question(self, request: HttpRequest, queryset: QuerySet[Question]) -> None: 
        for item in queryset: 
            item.publish() 

    @admin.action(description="Update model information")
    def update_model(self, request: HttpRequest, queryset: QuerySet[Question]) -> None: 
        for item in queryset: 
            item.get_updated_model() 


admin.site.register(Question, QuestionsAdmin)