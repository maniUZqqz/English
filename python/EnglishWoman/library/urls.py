from django.urls import path
from . import views

urlpatterns = [
    path('', views.library_page, name='library'),
    path('book/<int:pk>/', views.book_detail, name='book_detail'),
    path('book/<int:pk>/delete/', views.delete_book, name='delete_book'),
    path('section/<int:pk>/', views.section_detail, name='section_detail'),
    path('section/<int:pk>/teach/', views.teach_section, name='teach_section'),
    path('section/<int:pk>/quiz/', views.api_section_quiz, name='api_section_quiz'),
    path('section/<int:pk>/vocab/', views.api_section_vocab, name='api_section_vocab'),
]
