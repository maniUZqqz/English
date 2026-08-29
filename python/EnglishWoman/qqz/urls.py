from django.urls import path
from . import views

urlpatterns = [
    path('select-quiz/', views.select_quiz, name='select_quiz'),
    path('quiz/', views.quiz, name='quiz'),
    path('generate-quiz/', views.generate_quiz, name='generate_quiz'),
    path('submit-answer/', views.submit_quiz_answer, name='submit_quiz_answer'),
    path('Teach/', views.Teach, name='teach'),
]

