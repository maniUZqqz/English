"""تست‌های مسیرهای اصلی: احراز هویت، آزمون تعیین سطح، سهمیه و استریک. فراخوانی‌های AI ماک می‌شوند."""

import json
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import DailyActivity, Question, UserProfile, UserResponse
from .usage import QuotaExceeded, consume_ai_quota, current_streak, usage_today

FAKE_QUESTIONS = json.dumps([
    {
        "text": f"Question {i}?",
        "option1": "A", "option2": "B", "option3": "C", "option4": "D",
        "correct_option": 1,
    }
    for i in range(1, 4)
])


class AuthTests(TestCase):
    def test_register_creates_user_profile_and_logs_in(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'Str0ngPass!123',
            'password_confirm': 'Str0ngPass!123',
        })
        self.assertRedirects(response, reverse('home'))
        user = User.objects.get(username='newuser')
        # سیگنال باید پروفایل بسازد
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_register_password_mismatch_shows_error(self):
        response = self.client.post(reverse('register'), {
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'Str0ngPass!123',
            'password_confirm': 'different',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_anonymous_home_shows_landing(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'app/landing.html')

    def test_authenticated_home_shows_dashboard(self):
        User.objects.create_user('dash', password='pass12345')
        self.client.login(username='dash', password='pass12345')
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'app/home.html')
        self.assertContains(response, 'مصرف امروز AI')


class PlacementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('learner', password='pass12345')
        self.other = User.objects.create_user('other', password='pass12345')
        self.client.login(username='learner', password='pass12345')

    @patch('app.views.chat_completion', return_value=FAKE_QUESTIONS)
    def test_level_determination_creates_questions_only_for_current_user(self, _mock):
        # کاربر دیگر از قبل سوال دارد؛ نباید پاک شود
        other_q = Question.objects.create(
            user=self.other, text='Other q', option1='1', option2='2',
            option3='3', option4='4', correct_option=1,
        )
        response = self.client.get(reverse('level_determination'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Question.objects.filter(user=self.user).count(), 3)
        self.assertTrue(Question.objects.filter(pk=other_q.pk).exists())

    @patch('app.views.chat_completion', return_value='Good answer!')
    def test_submit_response_records_answer_and_progress(self, _mock):
        q1 = Question.objects.create(
            user=self.user, text='Q1', option1='A', option2='B',
            option3='C', option4='D', correct_option=2,
        )
        Question.objects.create(
            user=self.user, text='Q2', option1='A', option2='B',
            option3='C', option4='D', correct_option=1,
        )
        response = self.client.post(reverse('submit_response'), {
            'question_id': q1.id,
            'selected_option': 2,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['is_correct'])
        self.assertFalse(data['test_completed'])
        self.assertEqual(data['next_question']['text'], 'Q2')
        self.assertTrue(UserResponse.objects.filter(user=self.user, question=q1, is_correct=True).exists())
        # پیشرفت: 1 پاسخ صحیح از 2 سوال
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.progress, 50)

    def test_submit_response_rejects_other_users_question(self):
        q = Question.objects.create(
            user=self.other, text='Not yours', option1='A', option2='B',
            option3='C', option4='D', correct_option=1,
        )
        response = self.client.post(reverse('submit_response'), {
            'question_id': q.id,
            'selected_option': 1,
        })
        self.assertEqual(response.status_code, 404)


class QuotaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('quota', password='pass12345')

    @override_settings(AI_DAILY_LIMIT=2)
    def test_quota_enforced_after_limit(self):
        consume_ai_quota(self.user)
        consume_ai_quota(self.user)
        with self.assertRaises(QuotaExceeded):
            consume_ai_quota(self.user)
        used, limit = usage_today(self.user)
        self.assertEqual((used, limit), (2, 2))

    @override_settings(AI_DAILY_LIMIT=1)
    def test_level_determination_returns_quota_page_when_exhausted(self):
        self.client.login(username='quota', password='pass12345')
        consume_ai_quota(self.user)  # سهمیه را پر کن
        response = self.client.get(reverse('level_determination'))
        self.assertEqual(response.status_code, 429)
        self.assertTemplateUsed(response, 'app/quota_exceeded.html')


class StreakTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('streaky', password='pass12345')

    def test_no_activity_means_zero_streak(self):
        self.assertEqual(current_streak(self.user), 0)

    def test_consecutive_days_counted(self):
        today = timezone.localdate()
        for offset in (0, 1, 2):
            DailyActivity.objects.create(user=self.user, date=today - timedelta(days=offset))
        self.assertEqual(current_streak(self.user), 3)

    def test_streak_survives_until_end_of_today(self):
        # دیروز و پریروز فعال بوده، امروز هنوز نه — زنجیره نباید صفر شود
        today = timezone.localdate()
        for offset in (1, 2):
            DailyActivity.objects.create(user=self.user, date=today - timedelta(days=offset))
        self.assertEqual(current_streak(self.user), 2)

    def test_gap_breaks_streak(self):
        today = timezone.localdate()
        DailyActivity.objects.create(user=self.user, date=today)
        DailyActivity.objects.create(user=self.user, date=today - timedelta(days=2))
        self.assertEqual(current_streak(self.user), 1)
