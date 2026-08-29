# models.py
from django.db import models
from django.contrib.auth.models import User

class Question(models.Model):
    # هر سوال متعلق به آزمون تعیین سطح یک کاربر مشخص است
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='placement_questions')
    text = models.TextField()
    option1 = models.CharField(max_length=255)
    option2 = models.CharField(max_length=255)
    option3 = models.CharField(max_length=255)
    option4 = models.CharField(max_length=255)
    correct_option = models.IntegerField()

    @property
    def options(self):
        return {
            1: self.option1,
            2: self.option2,
            3: self.option3,
            4: self.option4
        }

class UserResponse(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_option = models.IntegerField()
    is_correct = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

class UserLevel(models.Model):
    # OneToOne: هر کاربر دقیقاً یک سطح دارد (آزمون مجدد همان ردیف را به‌روز می‌کند)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    level_title = models.CharField(max_length=255)      # عنوان سطح کاربر
    level_explanation = models.TextField()             # توضیحات مربوط به سطح کاربر
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.level_title}"

class DailyActivity(models.Model):
    """فعالیت روزانه هر کاربر — پایه‌ی استریک و سهمیه مصرف AI."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='daily_activities')
    date = models.DateField()
    ai_requests = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.username} @ {self.date}: {self.ai_requests} AI requests"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student / زبان‌آموز'),
        ('teacher', 'Teacher / معلم'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    progress = models.PositiveIntegerField(default=0)   # درصد پیشرفت
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    xp = models.PositiveIntegerField(default=0)         # امتیاز گیمیفیکیشن

    @property
    def is_teacher(self):
        return self.role == 'teacher'

    @property
    def xp_level(self):
        """هر ۱۰۰ امتیاز = یک سطح."""
        return self.xp // 100 + 1

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()} - {self.progress}%"


class AIConfig(models.Model):
    """
    تنظیمات هوش مصنوعی — از پنل ادمین قابل ویرایش است.
    هر فیلدی که خالی/صفر باشد، مقدار .env (یا پیش‌فرض) استفاده می‌شود.
    فقط یک ردیف از این مدل ساخته می‌شود (singleton).
    """
    api_key = models.CharField(
        max_length=255, blank=True,
        help_text='کلید API (مثلاً MetisAI). خالی بماند تا از .env خوانده شود.',
    )
    base_url = models.CharField(
        max_length=255, blank=True,
        help_text='آدرس پایه API سازگار با OpenAI. خالی = مقدار .env',
    )
    model_name = models.CharField(
        max_length=100, blank=True,
        help_text='نام مدل (مثلاً gpt-4o-mini). خالی = مقدار .env',
    )
    daily_limit = models.PositiveIntegerField(
        default=0,
        help_text='سقف درخواست AI هر کاربر در روز. صفر = مقدار .env',
    )
    is_active = models.BooleanField(
        default=True,
        help_text='اگر خاموش شود، همه‌ی قابلیت‌های AI موقتاً غیرفعال می‌شوند.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'AI Configuration'
        verbose_name_plural = 'AI Configuration'

    def save(self, *args, **kwargs):
        # singleton: همیشه همان ردیف اول
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        return cls.objects.filter(pk=1).first()

    def __str__(self):
        return f"AI Config (model={self.model_name or 'from .env'}, active={self.is_active})"



# python manage.py makemigrations
# python manage.py migrate

