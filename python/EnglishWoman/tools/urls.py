from django.urls import path
from . import views

urlpatterns = [
    # صفحات
    path('chat/', views.chat_page, name='tool_chat'),
    path('story/', views.story_page, name='tool_story'),
    path('voice/', views.voice_page, name='tool_voice'),
    path('grammar/', views.grammar_page, name='tool_grammar'),
    path('dictionary/', views.dictionary_page, name='tool_dictionary'),
    path('wordbank/', views.wordbank_page, name='tool_wordbank'),
    path('review/', views.review_page, name='tool_review'),
    path('listening/', views.listening_page, name='tool_listening'),
    path('writing/', views.writing_page, name='tool_writing'),
    path('pronunciation/', views.pronunciation_page, name='tool_pronunciation'),
    # APIها
    path('api/chat/', views.api_chat, name='api_chat'),
    path('api/chat/clear/', views.api_chat_clear, name='api_chat_clear'),
    path('api/review/', views.api_review_word, name='api_review_word'),
    path('api/listening/', views.api_listening, name='api_listening'),
    path('api/writing/prompt/', views.api_writing_prompt, name='api_writing_prompt'),
    path('api/writing/score/', views.api_writing_score, name='api_writing_score'),
    path('api/pron/sentences/', views.api_pron_sentences, name='api_pron_sentences'),
    path('api/story/', views.api_story, name='api_story'),
    path('api/voice/', views.api_voice, name='api_voice'),
    path('api/grammar/', views.api_grammar, name='api_grammar'),
    path('api/translate/', views.api_translate, name='api_translate'),
    path('api/save-word/', views.api_save_word, name='api_save_word'),
    path('api/delete-word/', views.api_delete_word, name='api_delete_word'),
]
