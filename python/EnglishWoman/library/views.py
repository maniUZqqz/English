"""معلم PDF: آپلود کتاب، استخراج و بخش‌بندی متن، درس‌دادن هر بخش با AI."""

import json
import re

import markdown
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from app.usage import QuotaExceeded, award_xp, consume_ai_quota, record_activity
from app.views import quota_exceeded_page
from EnglishWoman.services import AIDisabled, chat_completion, extract_json, strip_code_fence
from app.models import UserLevel
from django.utils.html import strip_tags
from .models import Book, BookSection, SectionLesson

MAX_PDF_MB = 20
SECTION_CHARS = 1600   # طول تقریبی هر بخش
MAX_SECTIONS = 80      # سقف بخش‌ها برای کتاب‌های خیلی بلند

AI_NOT_CONFIGURED = 'هوش مصنوعی هنوز راه‌اندازی نشده است. مدیر باید کلید API را در پنل ادمین وارد کند.'


def _level_note(user):
    level = UserLevel.objects.filter(user=user).first()
    if not level:
        return ''
    title = strip_tags(level.level_title).strip()
    return f" The learner's English level is: {title}." if title else ''


def extract_pdf_text(django_file):
    """استخراج متن همه صفحات PDF. (در تست‌ها قابل ماک است)"""
    from pypdf import PdfReader
    reader = PdfReader(django_file)
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or '')
        except Exception:
            pages.append('')
    return '\n'.join(pages), len(reader.pages)


def split_into_sections(text, size=SECTION_CHARS):
    """بخش‌بندی متن روی مرز جمله/پاراگراف، حدوداً size کاراکتر."""
    text = re.sub(r'[ \t]+', ' ', text).strip()
    if not text:
        return []
    sentences = re.split(r'(?<=[.!?؟])\s+|\n{2,}', text)
    sections, current = [], ''
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        if current and len(current) + len(sentence) > size:
            sections.append(current.strip())
            current = sentence
        else:
            current = f'{current} {sentence}'.strip()
        if len(sections) >= MAX_SECTIONS:
            break
    if current and len(sections) < MAX_SECTIONS:
        sections.append(current.strip())
    return sections


@login_required(login_url='login')
def library_page(request):
    """لیست کتاب‌ها + آپلود PDF جدید."""
    if request.method == 'POST':
        pdf = request.FILES.get('file')
        title = (request.POST.get('title') or '').strip()[:200]
        if not pdf:
            messages.error(request, 'یک فایل PDF انتخاب کنید.')
            return redirect('library')
        if not pdf.name.lower().endswith('.pdf'):
            messages.error(request, 'فقط فایل PDF مجاز است.')
            return redirect('library')
        if pdf.size > MAX_PDF_MB * 1024 * 1024:
            messages.error(request, f'حجم فایل نباید بیشتر از {MAX_PDF_MB} مگابایت باشد.')
            return redirect('library')

        try:
            text, num_pages = extract_pdf_text(pdf)
        except Exception as e:
            print('PDF extract error:', e)
            messages.error(request, 'خواندن این PDF ممکن نبود — فایل سالم و متنی (غیراسکن) آپلود کنید.')
            return redirect('library')

        sections = split_into_sections(text)
        if len(sections) == 0 or len(text.strip()) < 200:
            messages.error(
                request,
                'متنی از این PDF استخراج نشد. اگر کتاب اسکن‌شده (عکسی) است، نسخه متنی آن را آپلود کنید.')
            return redirect('library')

        book = Book.objects.create(
            user=request.user,
            title=title or pdf.name.rsplit('.', 1)[0][:200],
            file=pdf,
            num_pages=num_pages,
        )
        BookSection.objects.bulk_create([
            BookSection(book=book, order=i + 1, text=s) for i, s in enumerate(sections)
        ])
        record_activity(request.user)
        messages.success(request, f'کتاب «{book.title}» آپلود شد — {len(sections)} بخش آماده یادگیری! 📚')
        return redirect('book_detail', pk=book.pk)

    books = Book.objects.filter(user=request.user).prefetch_related('sections')
    book_rows = [{
        'book': b,
        'section_count': b.sections.count(),
        'learned_count': SectionLesson.objects.filter(section__book=b).count(),
    } for b in books]
    return render(request, 'library/library.html', {'book_rows': book_rows, 'max_mb': MAX_PDF_MB})


@login_required(login_url='login')
def book_detail(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)
    learned_ids = set(
        SectionLesson.objects.filter(section__book=book).values_list('section_id', flat=True))
    sections = [{
        'section': s,
        'learned': s.id in learned_ids,
        'excerpt': s.text[:110],
    } for s in book.sections.all()]
    return render(request, 'library/book_detail.html', {
        'book': book,
        'sections': sections,
        'learned_count': len(learned_ids),
    })


@login_required(login_url='login')
def delete_book(request, pk):
    book = get_object_or_404(Book, pk=pk, user=request.user)
    if request.method == 'POST':
        book.file.delete(save=False)
        book.delete()
        messages.info(request, 'کتاب حذف شد.')
    return redirect('library')


@login_required(login_url='login')
def section_detail(request, pk):
    section = get_object_or_404(
        BookSection.objects.select_related('book'), pk=pk, book__user=request.user)
    lesson = SectionLesson.objects.filter(section=section).first()
    prev_section = section.book.sections.filter(order__lt=section.order).order_by('-order').first()
    next_section = section.book.sections.filter(order__gt=section.order).order_by('order').first()
    return render(request, 'library/section_detail.html', {
        'section': section,
        'book': section.book,
        'lesson': lesson,
        'prev_section': prev_section,
        'next_section': next_section,
    })


@login_required(login_url='login')
@require_POST
def teach_section(request, pk):
    """AI مثل یک معلم این بخش را درس می‌دهد — نتیجه کش می‌شود."""
    section = get_object_or_404(
        BookSection.objects.select_related('book'), pk=pk, book__user=request.user)
    if SectionLesson.objects.filter(section=section).exists():
        return redirect('section_detail', pk=pk)
    try:
        consume_ai_quota(request.user)
    except QuotaExceeded as e:
        return quota_exceeded_page(request, e)

    prompt = (
        'You are a friendly English teacher. Teach the following passage from a book '
        'to a Persian-speaking learner.' + _level_note(request.user) + '\n\n'
        'Produce a Markdown lesson with these sections:\n'
        '## خلاصه (a 2-3 sentence Persian summary of the passage)\n'
        '## لغات کلیدی (a Markdown table: word | معنی فارسی | example from the passage)\n'
        '## نکات گرامری (2-3 grammar points found in the passage, explained simply in Persian with the English examples)\n'
        '## ترجمه (a fluent Persian translation of the passage)\n\n'
        f'Passage:\n{section.text[:4000]}'
    )
    try:
        md_content = chat_completion([
            {'role': 'system', 'content': 'You are a helpful bilingual English teacher for Persian speakers.'},
            {'role': 'user', 'content': prompt},
        ])
        html = markdown.markdown(strip_code_fence(md_content), extensions=['tables'])
        SectionLesson.objects.create(section=section, lesson_html=html)
        award_xp(request.user, 5)
        messages.success(request, 'درس این بخش آماده شد! 🎓')
    except AIDisabled:
        return render(request, 'app/ai_error.html', status=503)
    except Exception as e:
        print('teach_section error:', e)
        messages.error(request, 'خطا در تولید درس — دوباره تلاش کنید.')
    return redirect('section_detail', pk=pk)


@login_required(login_url='login')
@require_POST
def api_section_quiz(request, pk):
    """۳ سوال درک مطلب از این بخش (تصحیح سمت کلاینت مثل تمرین شنیداری)."""
    section = get_object_or_404(
        BookSection.objects.select_related('book'), pk=pk, book__user=request.user)
    try:
        consume_ai_quota(request.user)
    except QuotaExceeded as e:
        return JsonResponse({'error': str(e)}, status=429)
    try:
        prompt = (
            'Create 3 multiple-choice comprehension questions about this passage. '
            'Return ONLY a JSON object: {"questions": [{"question": "...", '
            '"options": ["...", "...", "...", "..."], "answer": 0}]} '
            'where "answer" is the index (0-3) of the correct option.\n\n'
            f'Passage:\n{section.text[:4000]}'
        )
        reply = chat_completion([
            {'role': 'system', 'content': 'You create reading comprehension quizzes.'},
            {'role': 'user', 'content': prompt},
        ])
        parsed = extract_json(reply)
        questions = parsed.get('questions', [])
        if not questions:
            return JsonResponse({'error': 'Invalid quiz from AI.'}, status=500)
        return JsonResponse({'questions': questions})
    except AIDisabled:
        return JsonResponse({'error': AI_NOT_CONFIGURED}, status=503)
    except Exception as e:
        print('api_section_quiz error:', e)
        return JsonResponse({'error': 'Failed to create the quiz.'}, status=500)


@login_required(login_url='login')
@require_POST
def api_section_vocab(request, pk):
    """استخراج لغات مهم بخش + افزودن یک‌جا به دفتر لغات."""
    section = get_object_or_404(
        BookSection.objects.select_related('book'), pk=pk, book__user=request.user)
    try:
        consume_ai_quota(request.user)
    except QuotaExceeded as e:
        return JsonResponse({'error': str(e)}, status=429)
    try:
        prompt = (
            'Extract the 8 most useful vocabulary words for an English learner from this passage.'
            + _level_note(request.user) +
            ' Return ONLY a JSON object: {"words": [{"word": "...", "translation": "معنی فارسی", '
            '"example": "sentence from the passage containing the word"}]}\n\n'
            f'Passage:\n{section.text[:4000]}'
        )
        reply = chat_completion([
            {'role': 'system', 'content': 'You extract key vocabulary for Persian-speaking English learners.'},
            {'role': 'user', 'content': prompt},
        ])
        parsed = extract_json(reply)
        words = parsed.get('words', [])[:10]

        from tools.models import SavedWord
        added = 0
        for w in words:
            word = str(w.get('word', '')).strip()[:100]
            if not word:
                continue
            _, created = SavedWord.objects.update_or_create(
                user=request.user, word=word,
                defaults={
                    'translation': str(w.get('translation', ''))[:255],
                    'example': str(w.get('example', ''))[:2000],
                },
            )
            if created:
                added += 1
        record_activity(request.user)
        return JsonResponse({'words': words, 'added': added})
    except AIDisabled:
        return JsonResponse({'error': AI_NOT_CONFIGURED}, status=503)
    except Exception as e:
        print('api_section_vocab error:', e)
        return JsonResponse({'error': 'Failed to extract vocabulary.'}, status=500)
