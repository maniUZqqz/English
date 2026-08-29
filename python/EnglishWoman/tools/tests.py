"""تست‌های ابزارهای AI: احراز هویت، سهمیه، و دفتر لغات. فراخوانی‌های AI ماک می‌شوند."""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import SavedWord


class ToolPagesTests(TestCase):
    PAGES = ('tool_chat', 'tool_story', 'tool_voice', 'tool_grammar',
             'tool_dictionary', 'tool_wordbank', 'tool_review', 'tool_listening')

    def test_tool_pages_require_login(self):
        for name in self.PAGES:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 302, name)
            self.assertIn(reverse('login'), response.url, name)

    def test_tool_pages_render_for_authenticated_user(self):
        User.objects.create_user('tooluser', password='pass12345')
        self.client.login(username='tooluser', password='pass12345')
        for name in self.PAGES:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 200, name)


class ToolApiTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('apiuser', password='pass12345')
        self.client.login(username='apiuser', password='pass12345')

    def _post(self, url_name, payload):
        return self.client.post(
            reverse(url_name), data=json.dumps(payload), content_type='application/json'
        )

    @patch('tools.views.chat_completion', return_value='Corrected: Hello world.')
    def test_grammar_api_returns_result(self, mock_chat):
        response = self._post('api_grammar', {'text': 'helo world'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], 'Corrected: Hello world.')
        mock_chat.assert_called_once()

    @patch('tools.views.chat_completion', return_value='Hi! Great sentence.')
    def test_chat_api_persists_memory_and_clears(self, mock_chat):
        from .models import ChatMessage
        # پیام اول ذخیره می‌شود
        response = self._post('api_chat', {'message': 'Hello teacher'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ChatMessage.objects.filter(user=self.user).count(), 2)
        # پیام دوم باید تاریخچه را در context داشته باشد و system سمت سرور باشد
        self._post('api_chat', {'message': 'How are you?'})
        sent_messages = mock_chat.call_args.args[0]
        self.assertEqual(sent_messages[0]['role'], 'system')
        self.assertIn({'role': 'user', 'content': 'Hello teacher'}, sent_messages)
        # پاک کردن حافظه
        response = self._post('api_chat_clear', {})
        self.assertTrue(response.json()['cleared'])
        self.assertEqual(ChatMessage.objects.filter(user=self.user).count(), 0)

    @patch('tools.views.chat_completion', return_value=json.dumps({
        'translation': 'سلام', 'synonyms': 'hi', 'antonyms': '', 'example': '**hello** there',
    }))
    def test_translate_api_parses_json(self, _mock):
        response = self._post('api_translate', {
            'text': 'hello', 'sourceLang': 'English', 'targetLang': 'Persian',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['translation'], 'سلام')
        self.assertTrue(data['is_single_word'])

    @override_settings(AI_DAILY_LIMIT=1)
    @patch('tools.views.chat_completion', return_value='ok')
    def test_quota_returns_429_after_limit(self, _mock):
        first = self._post('api_grammar', {'text': 'one'})
        self.assertEqual(first.status_code, 200)
        second = self._post('api_grammar', {'text': 'two'})
        self.assertEqual(second.status_code, 429)
        self.assertIn('سهمیه', second.json()['error'])


class WordBankTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('wordy', password='pass12345')
        self.client.login(username='wordy', password='pass12345')

    def _post(self, url_name, payload):
        return self.client.post(
            reverse(url_name), data=json.dumps(payload), content_type='application/json'
        )

    def test_save_word_and_show_in_wordbank(self):
        response = self._post('api_save_word', {
            'word': 'serendipity', 'translation': 'خوش‌اقبالی',
            'synonyms': 'luck', 'antonyms': 'misfortune', 'example': 'A moment.',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['saved'])
        page = self.client.get(reverse('tool_wordbank'))
        self.assertContains(page, 'serendipity')

    def test_save_word_is_idempotent_per_user(self):
        for _ in range(2):
            self._post('api_save_word', {'word': 'echo', 'translation': 'پژواک'})
        self.assertEqual(SavedWord.objects.filter(user=self.user, word='echo').count(), 1)

    def test_delete_word_only_own(self):
        other = User.objects.create_user('other', password='pass12345')
        other_word = SavedWord.objects.create(user=other, word='private')
        response = self._post('api_delete_word', {'id': other_word.id})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()['deleted'])
        self.assertTrue(SavedWord.objects.filter(pk=other_word.pk).exists())


class WritingTests(TestCase):
    """سیستم نوشتاری: تولید موضوع و تصحیح با نمره آیلتس."""

    def setUp(self):
        self.user = User.objects.create_user('writer', password='pass12345')
        self.client.login(username='writer', password='pass12345')

    def _post(self, url_name, payload):
        return self.client.post(
            reverse(url_name), data=json.dumps(payload), content_type='application/json')

    @patch('tools.views.chat_completion', return_value='{"prompt": "Describe your city."}')
    def test_writing_prompt(self, _mock):
        response = self._post('api_writing_prompt', {'style': 'general'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['prompt'], 'Describe your city.')

    @patch('tools.views.chat_completion', return_value=json.dumps({
        'score': 72, 'band': '6.0', 'feedback': 'Good effort.',
        'corrections': [{'original': 'I goes', 'corrected': 'I go', 'explanation': 'verb'}],
        'improved_version': 'My improved essay.',
    }))
    def test_writing_score_saves_history(self, _mock):
        from .models import WritingSubmission
        response = self._post('api_writing_score', {
            'prompt': 'Describe your city.',
            'text': 'My city is very beautiful and I love walking there every single day.',
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['score'], 72)
        self.assertEqual(data['band'], '6.0')
        submission = WritingSubmission.objects.get(user=self.user)
        self.assertEqual(submission.score, 72)
        # صفحه تاریخچه
        page = self.client.get(reverse('tool_writing'))
        self.assertContains(page, '6.0')

    def test_too_short_essay_rejected(self):
        response = self._post('api_writing_score', {'prompt': '', 'text': 'Too short.'})
        self.assertEqual(response.status_code, 400)

    @patch('tools.views.chat_completion', return_value='{"sentences": ["One.", "Two.", "Three."]}')
    def test_pron_sentences(self, _mock):
        response = self._post('api_pron_sentences', {'topic': 'food'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['sentences']), 3)


class SkillsPageTests(TestCase):
    def test_skills_page_renders(self):
        User.objects.create_user('skiller', password='pass12345')
        self.client.login(username='skiller', password='pass12345')
        page = self.client.get(reverse('skills'))
        self.assertEqual(page.status_code, 200)
        for word in ('گرامر', 'لغت', 'شنیداری', 'نوشتاری', 'اسپیکینگ'):
            self.assertContains(page, word)


class LeitnerTests(TestCase):
    """مرور فاصله‌دار لایتنر روی دفتر لغات."""

    def setUp(self):
        self.user = User.objects.create_user('leitner', password='pass12345')
        self.client.login(username='leitner', password='pass12345')

    def _review(self, word_id, known):
        return self.client.post(
            reverse('api_review_word'),
            data=json.dumps({'id': word_id, 'known': known}),
            content_type='application/json',
        )

    def test_known_moves_word_up_a_box(self):
        from datetime import timedelta
        from django.utils import timezone
        word = SavedWord.objects.create(user=self.user, word='cat')
        response = self._review(word.id, True)
        self.assertEqual(response.status_code, 200)
        word.refresh_from_db()
        self.assertEqual(word.box, 2)
        self.assertEqual(word.next_review, timezone.localdate() + timedelta(days=2))

    def test_unknown_resets_to_box_one(self):
        from datetime import timedelta
        from django.utils import timezone
        word = SavedWord.objects.create(user=self.user, word='dog', box=4)
        self._review(word.id, False)
        word.refresh_from_db()
        self.assertEqual(word.box, 1)
        self.assertEqual(word.next_review, timezone.localdate() + timedelta(days=1))

    def test_box_caps_at_five(self):
        word = SavedWord.objects.create(user=self.user, word='sun', box=5)
        self._review(word.id, True)
        word.refresh_from_db()
        self.assertEqual(word.box, 5)

    def test_review_page_shows_only_due_words(self):
        from datetime import timedelta
        from django.utils import timezone
        SavedWord.objects.create(user=self.user, word='due-word')
        SavedWord.objects.create(
            user=self.user, word='future-word',
            next_review=timezone.localdate() + timedelta(days=5),
        )
        page = self.client.get(reverse('tool_review'))
        self.assertContains(page, 'due-word')
        self.assertNotContains(page, 'future-word')
