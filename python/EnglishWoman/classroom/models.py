"""مدل‌های کلاس زبان: کلاس، اطلاعیه، تکلیف و تحویل تکلیف."""

import random
import string

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


def generate_join_code():
    """کد عضویت ۶ حرفی یکتا (بدون کاراکترهای گیج‌کننده مثل O و 0)."""
    alphabet = ''.join(c for c in string.ascii_uppercase + string.digits if c not in 'O0I1L')
    for _ in range(20):
        code = ''.join(random.choices(alphabet, k=6))
        if not Classroom.objects.filter(join_code=code).exists():
            return code
    return ''.join(random.choices(alphabet, k=8))  # عملاً غیرممکن است به اینجا برسیم


class Classroom(models.Model):
    LEVEL_CHOICES = [
        ('A1', 'A1 — Beginner'),
        ('A2', 'A2 — Elementary'),
        ('B1', 'B1 — Intermediate'),
        ('B2', 'B2 — Upper Intermediate'),
        ('C1', 'C1 — Advanced'),
        ('C2', 'C2 — Proficient'),
        ('mixed', 'Mixed levels'),
    ]

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='mixed')
    teacher = models.ForeignKey(User, on_delete=models.CASCADE, related_name='teaching_classes')
    students = models.ManyToManyField(User, related_name='enrolled_classes', blank=True)
    join_code = models.CharField(max_length=8, unique=True, default=generate_join_code)
    live_url = models.URLField(
        blank=True,
        help_text='لینک جلسه آنلاین (اسکای‌روم، گوگل‌میت…). خالی = اتاق خودکار Jitsi',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def live_link(self):
        """لینک کلاس زنده: سفارشی معلم یا اتاق خودکار Jitsi (رایگان، بدون ثبت‌نام)."""
        return self.live_url or f'https://meet.jit.si/EnglishLady-{self.join_code}'

    def __str__(self):
        return f"{self.name} ({self.get_level_display()}) — {self.teacher.username}"


class Announcement(models.Model):
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=200)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.classroom.name}] {self.title}"


class Assignment(models.Model):
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=200)
    description = models.TextField()
    due_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def is_past_due(self):
        return bool(self.due_date and timezone.now() > self.due_date)

    def __str__(self):
        return f"[{self.classroom.name}] {self.title}"


class Submission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='submissions')
    text = models.TextField()
    file = models.FileField(upload_to='submissions/%Y/%m/', blank=True)  # پیوست اختیاری
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    grade = models.PositiveIntegerField(null=True, blank=True)  # 0 تا 100
    feedback = models.TextField(blank=True)

    class Meta:
        unique_together = ('assignment', 'student')
        ordering = ['-submitted_at']

    @property
    def is_graded(self):
        return self.grade is not None

    def __str__(self):
        return f"{self.student.username} → {self.assignment.title}"


class Comment(models.Model):
    """گفتگوی زیر هر تکلیف — پرسش‌وپاسخ بین معلم و زبان‌آموزها."""
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='class_comments')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username}: {self.text[:40]}"


class ClassSchedule(models.Model):
    """برنامه هفتگی کلاس — روز و ساعت جلسات تکرارشونده."""
    # شماره‌ها مطابق weekday() پایتون: دوشنبه=0 … یکشنبه=6
    WEEKDAY_CHOICES = [
        (5, 'شنبه'), (6, 'یکشنبه'), (0, 'دوشنبه'), (1, 'سه‌شنبه'),
        (2, 'چهارشنبه'), (3, 'پنجشنبه'), (4, 'جمعه'),
    ]

    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='schedules')
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ['weekday', 'start_time']

    def __str__(self):
        return f"{self.classroom.name}: {self.get_weekday_display()} {self.start_time:%H:%M}"


class ClassSession(models.Model):
    """یک جلسه برگزارشده — پایه حضور و غیاب."""
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='sessions')
    date = models.DateField()
    topic = models.CharField(max_length=200, blank=True)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('classroom', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.classroom.name} — {self.date}"


class Attendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'حاضر'),
        ('absent', 'غایب'),
        ('late', 'تأخیر'),
        ('excused', 'موجه'),
    ]

    session = models.ForeignKey(ClassSession, on_delete=models.CASCADE, related_name='attendances')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='attendances')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='present')

    class Meta:
        unique_together = ('session', 'student')

    def __str__(self):
        return f"{self.student.username} — {self.session.date}: {self.get_status_display()}"


class ClassExam(models.Model):
    """آزمون کلاسی — معلم می‌سازد (دستی یا با AI)، زبان‌آموز یک بار شرکت می‌کند."""
    classroom = models.ForeignKey(Classroom, on_delete=models.CASCADE, related_name='exams')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    duration_minutes = models.PositiveIntegerField(default=15)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.classroom.name}] {self.title}"


class ExamQuestion(models.Model):
    OPTION_CHOICES = [('A', 'A'), ('B', 'B'), ('C', 'C'), ('D', 'D')]

    exam = models.ForeignKey(ClassExam, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(max_length=1, choices=OPTION_CHOICES)

    def __str__(self):
        return self.text[:50]


class ExamAttempt(models.Model):
    exam = models.ForeignKey(ClassExam, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exam_attempts')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveIntegerField(null=True, blank=True)  # درصد ۰ تا ۱۰۰

    class Meta:
        unique_together = ('exam', 'student')

    def __str__(self):
        return f"{self.student.username} — {self.exam.title}: {self.score}"


class ExamAnswer(models.Model):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(ExamQuestion, on_delete=models.CASCADE)
    selected = models.CharField(max_length=1, choices=ExamQuestion.OPTION_CHOICES, blank=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        unique_together = ('attempt', 'question')
