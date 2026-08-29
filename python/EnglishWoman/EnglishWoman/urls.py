from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app.urls')),
    path('qqz/', include('qqz.urls')),
    path('tools/', include('tools.urls')),
    path('classes/', include('classroom.urls')),
    path('library/', include('library.urls')),
    path('billing/', include('billing.urls')),

    # بازیابی رمز عبور (در حالت توسعه، ایمیل در کنسول چاپ می‌شود)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='app/password_reset_form.html',
        email_template_name='app/password_reset_email.txt',
        subject_template_name='app/password_reset_subject.txt',
    ), name='password_reset'),
    path('password-reset/sent/', auth_views.PasswordResetDoneView.as_view(
        template_name='app/password_reset_done.html'), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='app/password_reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='app/password_reset_complete.html'), name='password_reset_complete'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
