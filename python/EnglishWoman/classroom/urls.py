from django.urls import path
from . import views

urlpatterns = [
    path('', views.my_classes, name='my_classes'),
    path('join/', views.join_class, name='join_class'),
    path('create/', views.create_class, name='create_class'),
    path('<int:pk>/', views.class_detail, name='class_detail'),
    path('<int:pk>/leave/', views.leave_class, name='leave_class'),
    path('<int:pk>/announce/', views.add_announcement, name='add_announcement'),
    path('<int:pk>/assignments/new/', views.add_assignment, name='add_assignment'),
    path('<int:pk>/remove/<int:student_id>/', views.remove_student, name='remove_student'),
    # برنامه هفتگی و جلسات
    path('<int:pk>/schedule/add/', views.add_schedule, name='add_schedule'),
    path('<int:pk>/schedule/<int:schedule_id>/delete/', views.delete_schedule, name='delete_schedule'),
    path('<int:pk>/sessions/new/', views.add_session, name='add_session'),
    path('session/<int:pk>/', views.session_detail, name='session_detail'),
    # آزمون کلاسی
    path('<int:pk>/exams/new/', views.create_exam, name='create_exam'),
    path('exam/<int:pk>/', views.exam_detail, name='exam_detail'),
    path('exam/<int:pk>/questions/add/', views.add_exam_question, name='add_exam_question'),
    path('exam/<int:pk>/questions/<int:question_id>/delete/', views.delete_exam_question, name='delete_exam_question'),
    path('exam/<int:pk>/ai-questions/', views.ai_exam_questions, name='ai_exam_questions'),
    path('exam/<int:pk>/publish/', views.publish_exam, name='publish_exam'),
    path('exam/<int:pk>/start/', views.start_exam, name='start_exam'),
    path('exam/<int:pk>/take/', views.take_exam, name='take_exam'),
    # کارنامه
    path('<int:pk>/report/', views.report_card, name='my_report_card'),
    path('<int:pk>/report/<int:student_id>/', views.report_card, name='report_card'),
    # تکلیف
    path('assignment/<int:pk>/', views.assignment_detail, name='assignment_detail'),
    path('assignment/<int:pk>/submit/', views.submit_assignment, name='submit_assignment'),
    path('assignment/<int:pk>/comment/', views.add_comment, name='add_comment'),
    path('submission/<int:pk>/grade/', views.grade_submission, name='grade_submission'),
]
