# models.py
from django.db import models
from django.contrib.auth.models import User
from app.models import UserLevel


class StudyMaterial(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    level = models.ForeignKey(UserLevel, on_delete=models.CASCADE)
    topic = models.CharField(max_length=255)  # عنوان مبحث گرامری
    content_md = models.TextField()
    content_html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'level', 'topic')  # هر کاربر برای هر مبحث یک درس‌نامه



class QuizQuestion(models.Model):
    study_material = models.ForeignKey(StudyMaterial, on_delete=models.CASCADE, related_name='quiz_questions')
    question_text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(
        max_length=1,
        choices=[
            ('A', 'Option A'),
            ('B', 'Option B'),
            ('C', 'Option C'),
            ('D', 'Option D'),
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.question_text[:50]


class QuizUserAnswer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    quiz_question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    selected_option = models.CharField(
        max_length=1,
        choices=[
            ('A', 'Option A'),
            ('B', 'Option B'),
            ('C', 'Option C'),
            ('D', 'Option D'),
        ]
    )
    is_correct = models.BooleanField(default=False)
    answered_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # تعیین خودکار صحت پاسخ
        self.is_correct = (self.selected_option == self.quiz_question.correct_option)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.username} - {self.quiz_question} - {self.selected_option}"




# python manage.py makemigrations
# python manage.py migrate



