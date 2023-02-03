from django.contrib import admin
from django.http import HttpRequest
from django.db.models import QuerySet
from .models import AuthUser, Reviewer, Question_SPPS, Question_MPPS


# Register your models here.
class Reviewer_Admin(admin.ModelAdmin): 
    list_display = [
        'os_user_id', 'user_name', 'is_active', 'is_main_admin'
    ] 
    search_fields = ['user_name']
    readonly_fields = ['user_name', 'is_active']
    actions = ['change_status']

    @admin.action(description="Activate/Deactivate selected reviewers")
    def change_status(self, request: HttpRequest, queryset: QuerySet[Reviewer]) -> None:
        """ Change the reviewers' status from active to inactive, and vice versa 
        """
        for item in queryset: 
            user = AuthUser.objects.get(os_user_id=item.os_user_id)
            if item.is_active: 
                item.is_active = False 
                user.is_reviewer = False 
            else: 
                item.is_active = True 
                user.is_reviewer = True 
            item.save() 
            user.save() 

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[Reviewer]) -> None:
        """ Override the default delete function 
        """
        for item in queryset: 
            item.delete()
        return super().delete_queryset(request, queryset)


class Questions_SPPS_Admin(admin.ModelAdmin): 
    list_display = [
        '__str__', 'question_name', 'difficulty', 'is_published'
    ]
    readonly_fields = [
        'question_id', 'question_type', 'allowed_etype', 'etype', 
        'model_mass', 'model_volume', 'model_SA', 'model_inertia', 
        'is_published', 'completion_count', 'reviewer_completion_count'
    ]
    exclude = ['thumbnail', 'completion_time', 'completion_feature_cnt', 'drawing_jpeg']
    search_fields = ['question_name']
    actions = ['publish_question']

    @admin.action(description="Publish/Hide selected questions")
    def publish_question(self, request: HttpRequest, queryset: QuerySet[Question_SPPS]) -> None: 
        for item in queryset: 
            item.publish() 


class Questions_MPPS_Admin(admin.ModelAdmin): 
    list_display = [
        '__str__', 'question_name', 'difficulty', 'is_published'
    ]
    readonly_fields = [
        'question_id', 'question_type', 'allowed_etype', 'etype', 'mid', 
        'model_mass', 'model_volume', 'model_SA', 
        'is_published', 'completion_count', 'reviewer_completion_count'
    ]
    exclude = ['thumbnail', 'completion_time', 'completion_feature_cnt', 'drawing_jpeg']
    search_fields = ['question_name']
    actions = ['publish_question']

    @admin.action(description="Publish/Hide selected questions")
    def publish_question(self, request: HttpRequest, queryset: QuerySet[Question_MPPS]) -> None: 
        for item in queryset: 
            item.publish() 


admin.site.register(Reviewer, Reviewer_Admin)
admin.site.register(Question_SPPS, Questions_SPPS_Admin)
admin.site.register(Question_MPPS, Questions_MPPS_Admin)