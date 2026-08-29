"""
ابزارهای هوش مصنوعی (پورت‌شده از پروژه‌ی Express به جنگو):
چت‌بات، داستان‌ساز، مکالمه صوتی، چک گرامر و دیکشنری هوشمند + دفتر لغات.

همه‌ی پرامپت‌های system سمت سرور تعریف می‌شوند (به ورودی کلاینت اعتماد نمی‌کنیم)
و اگر کاربر تعیین سطح کرده باشد، سطح او در پرامپت لحاظ می‌شود.
"""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.utils.html import strip_tags
from django.views.decorators.http import require_POST

from django.utils import timezone

from app.models import UserLevel
from app.usage import QuotaExceeded, award_xp, consume_ai_quota, record_activity
from EnglishWoman.services import AIDisabled, chat_completion, extract_json
from .models import ChatMessage, SavedWord, WritingSubmission

AI_NOT_CONFIGURED = 'هوش مصنوعی هنوز راه‌اندازی نشده است. مدیر باید کلید API را در پنل ادمین (AI Configuration) وارد کند.'

MAX_HISTORY = 20  # حداکثر پیام‌های تاریخچه که به مدل ارسال می‌شود


def _check_quota(user):
    """اگر سهمیه پر باشد پاسخ 429 برمی‌گرداند، وگرنه None."""
    try:
        consume_ai_quota(user)
        return None
    except QuotaExceeded as e:
        return JsonResponse({'error': str(e)}, status=429)


def _user_level_note(user):
    """توضیح سطح کاربر برای شخصی‌سازی پرامپت‌ها؛ اگر سطح ندارد رشته خالی."""
    level = UserLevel.objects.filter(user=user).order_by('-created_at').first()
    if not level:
        return ""
    title = strip_tags(level.level_title).strip()
    if not title:
        return ""
    return f" The learner's English level is: {title}. Adapt your vocabulary and explanations to this level."


def _client_messages(request):
    """تاریخچه گفتگو را از بدنه JSON می‌خواند و پیام‌های system کلاینت را حذف می‌کند."""
    data = json.loads(request.body or '{}')
    messages = data.get('messages', [])
    cleaned = []
    for msg in messages[-MAX_HISTORY:]:
        role = msg.get('role')
        content = str(msg.get('content', ''))[:4000]
        if role in ('user', 'assistant') and content:
            cleaned.append({'role': role, 'content': content})
    return cleaned


# ---------- صفحات ----------

@login_required(login_url='login')
def chat_page(request):
    # حافظه گفتگو: تاریخچه از دیتابیس لود می‌شود
    history = ChatMessage.objects.filter(user=request.user).order_by('created_at')[:100]
    return render(request, 'tools/chat.html', {'history': history})


@login_required(login_url='login')
def story_page(request):
    return render(request, 'tools/story.html', {
        'prefill_words': request.GET.get('words', ''),
    })


@login_required(login_url='login')
def voice_page(request):
    return render(request, 'tools/voice.html')


@login_required(login_url='login')
def grammar_page(request):
    return render(request, 'tools/grammar.html')


@login_required(login_url='login')
def dictionary_page(request):
    return render(request, 'tools/dictionary.html')


@login_required(login_url='login')
def wordbank_page(request):
    words = SavedWord.objects.filter(user=request.user)
    due_count = words.filter(next_review__lte=timezone.localdate()).count()
    return render(request, 'tools/wordbank.html', {'words': words, 'due_count': due_count})


@login_required(login_url='login')
def review_page(request):
    """مرور فلش‌کارتی لایتنر — لغات سررسیدشده امروز."""
    due_words = SavedWord.objects.filter(
        user=request.user, next_review__lte=timezone.localdate(),
    ).order_by('box', 'next_review')
    cards = [{
        'id': w.id,
        'word': w.word,
        'translation': w.translation,
        'synonyms': w.synonyms,
        'example': w.example,
        'box': w.box,
    } for w in due_words]
    return render(request, 'tools/review.html', {
        'cards': cards,
        'total_words': SavedWord.objects.filter(user=request.user).count(),
    })


@login_required(login_url='login')
@require_POST
def api_review_word(request):
    """ثبت نتیجه مرور یک کارت: بلد بود → جعبه بالاتر، بلد نبود → جعبه ۱."""
    try:
        data = json.loads(request.body or '{}')
        word = SavedWord.objects.filter(user=request.user, id=data.get('id')).first()
        if not word:
            return JsonResponse({'error': 'Word not found.'}, status=404)
        word.mark_reviewed(known=bool(data.get('known')))
        award_xp(request.user, 1)
        return JsonResponse({'ok': True, 'box': word.box, 'next_review': str(word.next_review)})
    except Exception as e:
        print('api_review_word error:', e)
        return JsonResponse({'error': 'Failed to save review.'}, status=500)


@login_required(login_url='login')
def listening_page(request):
    return render(request, 'tools/listening.html')


@login_required(login_url='login')
def writing_page(request):
    """تمرین نوشتاری — با تاریخچه و روند نمره."""
    history = WritingSubmission.objects.filter(user=request.user)[:10]
    return render(request, 'tools/writing.html', {'history': history})


@login_required(login_url='login')
@require_POST
def api_writing_prompt(request):
    """تولید یک موضوع نوشتاری متناسب با سطح کاربر."""
    quota_error = _check_quota(request.user)
    if quota_error:
        return quota_error
    try:
        data = json.loads(request.body or '{}')
        style = str(data.get('style', 'general'))[:20]  # general یا ielts
        system_prompt = 'You create writing tasks for English learners.' + _user_level_note(request.user)
        if style == 'ielts':
            user_prompt = (
                'Give me ONE IELTS Writing Task 2 style question. '
                'Return ONLY a JSON object: {"prompt": "..."}'
            )
        else:
            user_prompt = (
                'Give me ONE short, interesting writing prompt (1-2 sentences) '
                'suitable for my level. Return ONLY a JSON object: {"prompt": "..."}'
            )
        reply = chat_completion([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ], temperature=0.9)
        parsed = extract_json(reply)
        return JsonResponse({'prompt': str(parsed.get('prompt', '')).strip()})
    except AIDisabled:
        return JsonResponse({'error': AI_NOT_CONFIGURED}, status=503)
    except Exception as e:
        print('api_writing_prompt error:', e)
        return JsonResponse({'error': 'Failed to create a prompt.'}, status=500)


@login_required(login_url='login')
@require_POST
def api_writing_score(request):
    """تصحیح و نمره‌دهی متن کاربر با معیار آیلتس + ذخیره در تاریخچه."""
    quota_error = _check_quota(request.user)
    if quota_error:
        return quota_error
    try:
        data = json.loads(request.body or '{}')
        prompt = str(data.get('prompt', '')).strip()[:1000]
        text = str(data.get('text', '')).strip()[:8000]
        if not text or len(text.split()) < 10:
            return JsonResponse({'error': 'متن خیلی کوتاه است — حداقل ۱۰ کلمه بنویسید.'}, status=400)

        system_prompt = (
            'You are an experienced IELTS writing examiner. Assess the student essay fairly.'
            + _user_level_note(request.user)
        )
        user_prompt = (
            f'Writing task: {prompt or "Free writing"}\n\n'
            f'Student essay:\n{text}\n\n'
            'Assess it and return ONLY a JSON object with these keys:\n'
            '{"score": 0-100, "band": "IELTS band like 6.5", '
            '"feedback": "3-5 sentences of concrete feedback in simple English", '
            '"corrections": [{"original": "...", "corrected": "...", "explanation": "short reason"}], '
            '"improved_version": "the corrected full essay"}'
        )
        reply = chat_completion([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ], temperature=0.3)
        parsed = extract_json(reply)

        submission = WritingSubmission.objects.create(
            user=request.user,
            prompt=prompt,
            text=text,
            score=min(int(parsed.get('score', 0) or 0), 100),
            band=str(parsed.get('band', ''))[:10],
            feedback=str(parsed.get('feedback', '')),
            improved_version=str(parsed.get('improved_version', '')),
        )
        award_xp(request.user, 10)  # تکمیل یک تمرین نوشتاری
        return JsonResponse({
            'score': submission.score,
            'band': submission.band,
            'feedback': submission.feedback,
            'corrections': parsed.get('corrections', [])[:20],
            'improved_version': submission.improved_version,
        })
    except AIDisabled:
        return JsonResponse({'error': AI_NOT_CONFIGURED}, status=503)
    except Exception as e:
        print('api_writing_score error:', e)
        return JsonResponse({'error': 'Failed to score the essay.'}, status=500)


@login_required(login_url='login')
def pronunciation_page(request):
    return render(request, 'tools/pronunciation.html')


@login_required(login_url='login')
@require_POST
def api_pron_sentences(request):
    """تولید ۵ جمله برای تمرین تلفظ متناسب با سطح."""
    quota_error = _check_quota(request.user)
    if quota_error:
        return quota_error
    try:
        data = json.loads(request.body or '{}')
        topic = str(data.get('topic', '')).strip()[:100] or 'everyday life'
        system_prompt = 'You create pronunciation practice sentences.' + _user_level_note(request.user)
        user_prompt = (
            f"Give me 5 natural English sentences about '{topic}' for pronunciation practice, "
            'each 6-12 words. Return ONLY a JSON object: {"sentences": ["...", "..."]}'
        )
        reply = chat_completion([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_prompt},
        ], temperature=0.8)
        parsed = extract_json(reply)
        sentences = [str(s) for s in parsed.get('sentences', [])][:5]
        if not sentences:
            return JsonResponse({'error': 'No sentences from AI.'}, status=500)
        return JsonResponse({'sentences': sentences})
    except AIDisabled:
        return JsonResponse({'error': AI_NOT_CONFIGURED}, status=503)
    except Exception as e:
        print('api_pron_sentences error:', e)
        return JsonResponse({'error': 'Failed to create sentences.'}, status=500)


@login_required(login_url='login')
@require_POST
def api_listening(request):
    """تولید تمرین شنیداری: متن کوتاه + ۳ سوال درک مطلب."""
    quota_error = _check_quota(request.user)
    if quota_error:
        return quota_error
    try:
        data = json.loads(request.body or '{}')
        topic = str(data.get('topic', '')).strip()[:100] or 'daily life'
        system_prompt = (
            'You create listening comprehension exercises for English learners.'
            + _user_level_note(request.user)
        )
        prompt = (
            f"Write a short spoken-style English passage (4-6 sentences) about '{topic}', "
            'then 3 multiple-choice comprehension questions about it. '
            'Return ONLY a JSON object like: '
            '{"passage": "...", "questions": [{"question": "...", '
            '"options": ["...", "...", "...", "..."], "answer": 0}]} '
            'where "answer" is the index (0-3) of the correct option.'
        )
        reply = chat_completion([
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt},
        ], temperature=0.7)
        parsed = extract_json(reply)
        passage = str(parsed.get('passage', ''))
        questions = parsed.get('questions', [])
        if not passage or not questions:
            return JsonResponse({'error': 'Invalid exercise from AI.'}, status=500)
        return JsonResponse({'passage': passage, 'questions': questions})
    except AIDisabled:
        return JsonResponse({'error': AI_NOT_CONFIGURED}, status=503)
    except Exception as e:
        print('api_listening error:', e)
        return JsonResponse({'error': 'Failed to generate exercise.'}, status=500)


# ---------- APIها ----------

@login_required(login_url='login')
@require_POST
def api_chat(request):
    quota_error = _check_quota(request.user)
    if quota_error:
        return quota_error
    try:
        data = json.loads(request.body or '{}')
        message = str(data.get('message', '')).strip()[:4000]
        if not message:
            return JsonResponse({'error': 'No message provided.'}, status=400)

        # حافظه: تاریخچه از دیتابیس ساخته می‌شود، نه از کلاینت
        history = list(
            ChatMessage.objects.filter(user=request.user)
            .order_by('-created_at')[:MAX_HISTORY]
        )[::-1]
        context = [{'role': m.role, 'content': m.content} for m in history]

        system_prompt = (
            'You are an English teacher specialized in Writing and Reading. '
            'You help users practice and improve their skills. '
            'You remember the conversation so far and build on it.'
            + _user_level_note(request.user)
        )
        reply = chat_completion(
            [{'role': 'system', 'content': system_prompt}]
            + context
            + [{'role': 'user', 'content': message}]
        )
        # ذخیره در حافظه گفتگو
        ChatMessage.objects.create(user=request.user, role='user', content=message)
        ChatMessage.objects.create(user=request.user, role='assistant', content=reply)
        return JsonResponse({'content': reply})
    except AIDisabled:
        return JsonResponse({'error': AI_NOT_CONFIGURED}, status=503)
    except Exception as e:
        print('api_chat error:', e)
        return JsonResponse({'error': 'Something went wrong!'}, status=500)


@login_required(login_url='login')
@require_POST
def api_chat_clear(request):
    """پاک کردن حافظه گفتگوی چت‌بات."""
    deleted, _ = ChatMessage.objects.filter(user=request.user).delete()
    return JsonResponse({'cleared': True, 'deleted': deleted})


@login_required(login_url='login')
@require_POST
def api_story(request):
    quota_error = _check_quota(request.user)
    if quota_error:
        return quota_error
    try:
        messages = _client_messages(request)
        if not messages:
            return JsonResponse({'error': 'No message provided.'}, status=400)
        system_prompt = (
            'You are a helpful assistant that creates short, very simple English stories '
            'including the words or topic the user gives, to help them memorize those words. '
            'Use each given word at least once, exactly as written.'
            + _user_level_note(request.user)
        )
        reply = chat_completion([{'role': 'system', 'content': system_prompt}] + messages)
        return JsonResponse({'content': reply})
    except AIDisabled:
        return JsonResponse({'error': AI_NOT_CONFIGURED}, status=503)
    except Exception as e:
        print('api_story error:', e)
        return JsonResponse({'error': 'Failed to generate story.'}, status=500)


@login_required(login_url='login')
@require_POST
def api_voice(request):
    quota_error = _check_quota(request.user)
    if quota_error:
        return quota_error
    try:
        data = json.loads(request.body or '{}')
        message = str(data.get('message', '')).strip()[:2000]
        if not message:
            return JsonResponse({'error': 'Message is missing.'}, status=400)
        system_prompt = (
            "You are an experienced and specialized English teacher focused on conversation practice. "
            "Your role is to help users improve their English speaking skills through interactive and "
            "natural dialogues. You understand all English accents and provide responses that are fluent, "
            "accurate, and appropriate to the user's language level. If the user communicates in a language "
            "other than English, politely ask them to continue in English. Use gentle corrections and "
            "constructive feedback, keep replies short (2-4 sentences) so they are easy to listen to, and "
            "always end with a question to keep the conversation going."
            + _user_level_note(request.user)
        )
        reply = chat_completion(
            [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': message}],
            temperature=0.7,
            max_tokens=800,
        )
        return JsonResponse({'reply': reply})
    except AIDisabled:
        return JsonResponse({'error': AI_NOT_CONFIGURED}, status=503)
    except Exception as e:
        print('api_voice error:', e)
        return JsonResponse({'error': 'Failed to process voice chat.'}, status=500)


@login_required(login_url='login')
@require_POST
def api_grammar(request):
    quota_error = _check_quota(request.user)
    if quota_error:
        return quota_error
    try:
        data = json.loads(request.body or '{}')
        text = str(data.get('text', '')).strip()[:4000]
        if not text:
            return JsonResponse({'error': 'Text is missing.'}, status=400)
        system_prompt = (
            'You are a helpful assistant that checks grammar and improves sentences in English. '
            'Provide the corrected sentence and also explain what was wrong, if needed. '
            'Respond in a concise text format (no JSON needed).'
        )
        reply = chat_completion(
            [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': 'Check the grammar of this English text:\n' + text},
            ],
            temperature=0.7,
        )
        return JsonResponse({'result': reply})
    except AIDisabled:
        return JsonResponse({'error': AI_NOT_CONFIGURED}, status=503)
    except Exception as e:
        print('api_grammar error:', e)
        return JsonResponse({'error': 'An error occurred while checking grammar.'}, status=500)


@login_required(login_url='login')
@require_POST
def api_translate(request):
    quota_error = _check_quota(request.user)
    if quota_error:
        return quota_error
    try:
        data = json.loads(request.body or '{}')
        text = str(data.get('text', '')).strip()[:2000]
        source_lang = str(data.get('sourceLang', 'English'))[:30]
        target_lang = str(data.get('targetLang', 'Persian'))[:30]
        if not text:
            return JsonResponse({'error': 'Missing text.'}, status=400)

        is_single_word = ' ' not in text
        system_prompt = (
            f'You are a helpful translation assistant. '
            f'When the user provides text in {source_lang}, translate it to {target_lang}. '
            f'If it is a single word, also provide synonyms and antonyms in {source_lang}, '
            f'and create an example sentence in {source_lang} containing the original word '
            f'wrapped in bold markdown like **word**. '
            f'You must ONLY respond with a valid JSON object (no code block markers). '
            f'The JSON must have these keys exactly: "translation", "synonyms", "antonyms", "example". '
            f'If synonyms, antonyms, or example do not apply, set them to an empty string "".'
        )
        user_prompt = (
            f'Text to translate: "{text}"\n'
            f'Source language: {source_lang}\n'
            f'Target language: {target_lang}\n'
            f'Is single word: {is_single_word}'
        )
        reply = chat_completion(
            [{'role': 'system', 'content': system_prompt}, {'role': 'user', 'content': user_prompt}],
            temperature=0.2,
        )
        try:
            parsed = extract_json(reply)
        except ValueError:
            print('api_translate: invalid JSON from AI:', reply)
            return JsonResponse({'error': 'Invalid JSON from AI.'}, status=500)

        return JsonResponse({
            'translation': parsed.get('translation', '') or '',
            'synonyms': parsed.get('synonyms', '') or '',
            'antonyms': parsed.get('antonyms', '') or '',
            'example': parsed.get('example', '') or '',
            'is_single_word': is_single_word,
        })
    except AIDisabled:
        return JsonResponse({'error': AI_NOT_CONFIGURED}, status=503)
    except Exception as e:
        print('api_translate error:', e)
        return JsonResponse({'error': 'Translation request failed.'}, status=500)


@login_required(login_url='login')
@require_POST
def api_save_word(request):
    try:
        data = json.loads(request.body or '{}')
        word = str(data.get('word', '')).strip()[:100]
        if not word:
            return JsonResponse({'error': 'Word is missing.'}, status=400)
        record_activity(request.user)  # ذخیره لغت فعالیت است ولی AI مصرف نمی‌کند
        obj, created = SavedWord.objects.update_or_create(
            user=request.user,
            word=word,
            defaults={
                'translation': str(data.get('translation', ''))[:255],
                'synonyms': str(data.get('synonyms', ''))[:255],
                'antonyms': str(data.get('antonyms', ''))[:255],
                'example': str(data.get('example', ''))[:2000],
            },
        )
        if created:
            award_xp(request.user, 1)
        return JsonResponse({'saved': True, 'created': created, 'id': obj.id})
    except Exception as e:
        print('api_save_word error:', e)
        return JsonResponse({'error': 'Failed to save word.'}, status=500)


@login_required(login_url='login')
@require_POST
def api_delete_word(request):
    try:
        data = json.loads(request.body or '{}')
        word_id = data.get('id')
        deleted, _ = SavedWord.objects.filter(user=request.user, id=word_id).delete()
        return JsonResponse({'deleted': bool(deleted)})
    except Exception as e:
        print('api_delete_word error:', e)
        return JsonResponse({'error': 'Failed to delete word.'}, status=500)
