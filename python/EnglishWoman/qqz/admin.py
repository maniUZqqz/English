from django.contrib import admin
from .models import StudyMaterial, QuizQuestion, QuizUserAnswer

@admin.register(StudyMaterial)
class StudyMaterialAdmin(admin.ModelAdmin):
    list_display = ('topic', 'user', 'level', 'created_at')
    search_fields = ('topic',)

admin.site.register(QuizQuestion)
admin.site.register(QuizUserAnswer)


