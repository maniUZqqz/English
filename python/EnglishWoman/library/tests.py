"""تست‌های معلم PDF — استخراج متن ماک می‌شود، AI هم ماک می‌شود."""

import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from .models import Book, BookSection, SectionLesson
from .views import split_into_sections

SAMPLE_TEXT = ' '.join(
    f'This is sentence number {i} of the sample book about learning English.'
    for i in range(120)
)


class SplitTests(TestCase):
    def test_split_respects_size(self):
        sections = split_into_sections(SAMPLE_TEXT, size=500)
        self.assertGreater(len(sections), 3)
        for s in sections:
            self.assertLessEqual(len(s), 600)  # کمی انعطاف روی مرز جمله

    def test_empty_text_gives_no_sections(self):
        self.assertEqual(split_into_sections('   '), [])


class UploadTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('reader', password='pass12345')
        self.client.login(username='reader', password='pass12345')

    @patch('library.views.extract_pdf_text', return_value=(SAMPLE_TEXT, 12))
    def test_upload_creates_book_and_sections(self, _mock):
        pdf = SimpleUploadedFile('mybook.pdf', b'%PDF-1.4 fake', content_type='application/pdf')
        response = self.client.post(reverse('library'), {'title': 'کتاب من', 'file': pdf})
        book = Book.objects.get(user=self.user)
        self.assertRedirects(response, reverse('book_detail', args=[book.pk]))
        self.assertEqual(book.title, 'کتاب من')
        self.assertEqual(book.num_pages, 12)
        self.assertGreater(book.sections.count(), 0)

    @patch('library.views.extract_pdf_text', return_value=('', 3))
    def test_scanned_pdf_rejected(self, _mock):
        pdf = SimpleUploadedFile('scan.pdf', b'%PDF-1.4 fake', content_type='application/pdf')
        self.client.post(reverse('library'), {'file': pdf}, follow=True)
        self.assertFalse(Book.objects.exists())

    def test_non_pdf_rejected(self):
        f = SimpleUploadedFile('notes.txt', b'hello', content_type='text/plain')
        self.client.post(reverse('library'), {'file': f})
        self.assertFalse(Book.objects.exists())


class TeachTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('reader', password='pass12345')
        self.client.login(username='reader', password='pass12345')
        self.book = Book.objects.create(user=self.user, title='B', file='books/x.pdf', num_pages=1)
        self.section = BookSection.objects.create(book=self.book, order=1, text='A short passage.')

    @patch('library.views.chat_completion', return_value='## خلاصه\nاین بخش درباره... است.')
    def test_teach_section_caches_lesson(self, mock_chat):
        self.client.post(reverse('teach_section', args=[self.section.pk]))
        self.assertTrue(SectionLesson.objects.filter(section=self.section).exists())
        # بار دوم فراخوانی AI تکرار نمی‌شود (کش)
        self.client.post(reverse('teach_section', args=[self.section.pk]))
        self.assertEqual(mock_chat.call_count, 1)
        page = self.client.get(reverse('section_detail', args=[self.section.pk]))
        self.assertContains(page, 'این بخش درباره')

    @patch('library.views.chat_completion', return_value=json.dumps({
        'words': [{'word': 'passage', 'translation': 'قطعه', 'example': 'A short passage.'}],
    }))
    def test_vocab_extraction_adds_to_wordbank(self, _mock):
        from tools.models import SavedWord
        response = self.client.post(
            reverse('api_section_vocab', args=[self.section.pk]),
            data='{}', content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['added'], 1)
        self.assertTrue(SavedWord.objects.filter(user=self.user, word='passage').exists())

    def test_other_users_book_is_hidden(self):
        User.objects.create_user('other', password='pass12345')
        self.client.login(username='other', password='pass12345')
        self.assertEqual(
            self.client.get(reverse('book_detail', args=[self.book.pk])).status_code, 404)
        self.assertEqual(
            self.client.get(reverse('section_detail', args=[self.section.pk])).status_code, 404)
