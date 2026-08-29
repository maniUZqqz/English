from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('test-completed/', views.test_completed, name='test-completed'),
    path('level_determination/', views.level_determination, name='level_determination'),
    path('submit-response/', views.submit_response, name='submit_response'),
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("skills/", views.skills_view, name="skills"),
    path("leaderboard/", views.leaderboard_view, name="leaderboard"),
]
