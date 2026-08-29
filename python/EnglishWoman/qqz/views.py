from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render, redirect
import markdown
import random
import json
from app.models import UserLevel
from app.usage import QuotaExceeded, award_xp, consume_ai_quota, record_activity
from app.views import quota_exceeded_page
from qqz.models import StudyMaterial, QuizQuestion, QuizUserAnswer
from EnglishWoman.services import chat_completion, extract_json


@login_required(login_url='login')
def Teach(request):
    user = request.user

    # دریافت یا ساخت سطح کاربر قبل از درخواست پیشنهاد موضوع
    level, _ = UserLevel.objects.get_or_create(
        user=user,
        defaults={
            'level_title': 'Beginner',
            'level_explanation': 'Default explanation.'
        }
    )

    topic = request.GET.get('topic', 'Present Simple')  # پیش‌فرض اگر چیزی وارد نشه

    # اگر گزینه‌ی پیشنهاد مبحث از هوش مصنوعی انتخاب شده باشد
    if request.GET.get('suggest_topic') == 'true':
        prompt = f"لطفاً تنها عنوان یک مبحث گرامری مناسب برای زبان‌آموز سطح {level.level_title} را بدون توضیحات اضافه پیشنهاد بده."
        conversation = [
            {"role": "system", "content": "You are a helpful English grammar tutor."},
            {"role": "user", "content": prompt}
        ]

        def clean_topic(topic_str):
            # حذف خطوط اضافی؛ تنها اولین خط را نگه می‌دارد
            topic_str = topic_str.split('\n')[0]
            # محدود کردن طول عنوان به 100 کاراکتر
            return topic_str.strip()[:100]

        try:
            consume_ai_quota(user)
            topic = chat_completion(conversation).strip()
            topic = clean_topic(topic)
        except QuotaExceeded as e:
            return quota_exceeded_page(request, e)
        except Exception as e:
            print("AI error:", e)
            topic = 'Present Simple'

    # دریافت تمامی درس‌نامه‌های موجود برای این کاربر و سطح
    study_materials = StudyMaterial.objects.filter(user=user, level=level)

    # بررسی اینکه آیا درس‌نامه‌ای برای موضوع جاری وجود دارد یا نه
    material = study_materials.filter(topic=topic).first()

    if material:
        html_content = material.content_html
    else:
        # تولید درس‌نامه جدید یک درخواست AI مصرف می‌کند (درس‌نامه‌های موجود کش شده‌اند)
        try:
            consume_ai_quota(user)
        except QuotaExceeded as e:
            return quota_exceeded_page(request, e)
        # ساخت prompt برای تولید درس‌نامه
        prompt = (
            f"یک درس‌نامه کامل گرامری به زبان انگلیسی درباره‌ی '{topic}' برای زبان‌آموز سطح {level.level_title} بنویس. "
            "مطالب زیر را شامل شود:\n"
            "- توضیح ساده و قابل فهم\n"
            "- ساختار گرامری با مثال\n"
            "- مثال‌های زیاد با ترجمه فارسی\n"
            "- موارد کاربرد\n"
            "- تمرین برای زبان‌آموز\n\n"
            "درس‌نامه را به صورت Markdown و با ساختار قابل خواندن (## عنوان، - لیست، مثال) تولید کن."
        )

        conversation = [
            {"role": "system", "content": "You are a helpful English grammar tutor."},
            {"role": "user", "content": prompt}
        ]

        try:
            md_content = chat_completion(conversation)
        except Exception as e:
            # درس‌نامه‌ی خراب کش نشود — صفحه خطای شفاف نمایش بده
            print("AI error:", e)
            return render(request, 'app/ai_error.html', status=503)

        # پاک‌سازی متن خروجی از AI
        md_content_clean = md_content.strip()

        if md_content_clean.startswith("```") and md_content_clean.endswith("```"):
            lines = md_content_clean.splitlines()
            if len(lines) >= 2 and lines[0].lstrip().startswith("```") and lines[-1].lstrip().startswith("```"):
                lines = lines[1:-1]
            md_content_clean = "\n".join(lines).strip()

        if md_content_clean.lower().startswith("markdown"):
            md_content_clean = md_content_clean[len("markdown"):].strip()

        html_content = markdown.markdown(md_content_clean)

        # ذخیره در دیتابیس برای موضوع خاص
        StudyMaterial.objects.update_or_create(
            user=user,
            level=level,
            topic=topic,
            defaults={
                'content_md': md_content_clean,
                'content_html': html_content
            }
        )
        award_xp(user, 5)  # ساخت درس‌نامه جدید

    return render(request, 'app/Teach.html', {
        'content': html_content,
        'topic': topic,
        'study_materials': study_materials  # ارسال لیست درس‌نامه‌ها به template
    })


@login_required(login_url='login')
def select_quiz(request):
    """
    ویو نمایش صفحه انتخاب درس‌نامه برای آزمون.
    """
    user = request.user
    study_materials = StudyMaterial.objects.filter(user=user)
    if not study_materials.exists():
        return render(request, 'app/quize.html', {'error': 'هیچ درس‌نامه‌ای موجود نیست.'})
    return render(request, 'app/select_quiz.html', {'study_materials': study_materials})


@login_required(login_url='login')
def quiz(request):
    """
    ویو آزمون:
    - کاربر پس از انتخاب درس‌نامه از صفحه قبل، با دریافت study_material_id، سوالات آزمون نمایش داده می‌شود.
    - در صورتی که سوالی برای آن درس‌نامه وجود نداشته باشد، ابتدا از هوش مصنوعی سوالات تولید شده و سپس نمایش داده می‌شود.
    """
    user = request.user
    study_material_id = request.GET.get('study_material_id')
    if not study_material_id:
        # اگر درس‌نامه انتخاب نشده باشد، کاربر را به صفحه انتخاب هدایت می‌کند.
        return redirect('select_quiz')

    try:
        study_material = StudyMaterial.objects.get(id=study_material_id, user=user)
    except StudyMaterial.DoesNotExist:
        return render(request, 'app/quize.html', {'error': 'درس‌نامه یافت نشد.'})

    quiz_questions = study_material.quiz_questions.all()
    total_questions = quiz_questions.count()

    # اگر برای درس‌نامه انتخاب‌شده سوالی وجود ندارد، از هوش مصنوعی سوالات تولید می‌شود.
    if total_questions == 0:
        try:
            consume_ai_quota(user)
        except QuotaExceeded as e:
            return quota_exceeded_page(request, e)
        prompt = (
            f"بر اساس متن درس‌نامه زیر، یک آزمون گرامر زبان انگلیسی با ۵ سوال چند گزینه‌ای تولید کن. "
            "هر سوال باید شامل گزینه‌های A, B, C, D باشد و تنها یک گزینه صحیح داشته باشد. "
            "لطفاً خروجی را به صورت JSON تولید کن به این شکل:\n"
            "[\n"
            "  {\n"
            '    "question_text": "متن سوال",\n'
            '    "option_a": "گزینه A",\n'
            '    "option_b": "گزینه B",\n'
            '    "option_c": "گزینه C",\n'
            '    "option_d": "گزینه D",\n'
            '    "correct_option": "A"\n'
            "  },\n"
            "  ...\n"
            "]\n\n"
            f"متن درس‌نامه:\n{study_material.content_md}"
        )
        conversation = [
            {"role": "system", "content": "You are a helpful quiz generator."},
            {"role": "user", "content": prompt}
        ]
        try:
            quiz_json = chat_completion(conversation)
            quiz_data = extract_json(quiz_json)
            # حذف سوالات قبلی (اگر هرچند که موجود نباشند)
            study_material.quiz_questions.all().delete()
            for q in quiz_data:
                QuizQuestion.objects.create(
                    study_material=study_material,
                    question_text=q.get('question_text'),
                    option_a=q.get('option_a'),
                    option_b=q.get('option_b'),
                    option_c=q.get('option_c'),
                    option_d=q.get('option_d'),
                    correct_option=q.get('correct_option')
                )
        except Exception as e:
            print("AI error:", e)
            return render(request, 'app/quize.html', {'error': 'خطا در دریافت سوالات آزمون از هوش مصنوعی.'})
        # دریافت دوباره سوالات تولید شده
        quiz_questions = study_material.quiz_questions.all()
        total_questions = quiz_questions.count()

    # افزودن لیست گزینه‌ها به هر سوال برای نمایش در فرانت‌اند
    for q in quiz_questions:
        q.options = [q.option_a, q.option_b, q.option_c, q.option_d]

    context = {
        'study_material': study_material,
        'quiz_questions': quiz_questions,
        'total_questions': total_questions,
    }
    return render(request, 'app/quize.html', context)


@login_required(login_url='login')
def generate_quiz(request):
    """
    ویو تولید آزمون به صورت خودکار: در صورتی که بخواهید از میان درس‌نامه‌های موجود یک درس‌نامه انتخاب شود و سوالات از هوش مصنوعی تولید گردد.
    """
    user = request.user

    study_materials = StudyMaterial.objects.filter(user=user)
    if not study_materials.exists():
        return render(request, 'app/quize.html', {'error': 'هیچ درس‌نامه‌ای موجود نیست.'})

    study_material = random.choice(list(study_materials))

    try:
        consume_ai_quota(user)
    except QuotaExceeded as e:
        return quota_exceeded_page(request, e)

    prompt = (
        f"بر اساس متن درس‌نامه زیر، یک آزمون گرامر زبان انگلیسی با ۵ سوال چند گزینه‌ای تولید کن. "
        "هر سوال باید شامل گزینه‌های A, B, C, D باشد و تنها یک گزینه صحیح داشته باشد. "
        "لطفاً خروجی را به صورت JSON تولید کن به این شکل:\n"
        "[\n"
        "  {\n"
        '    "question_text": "متن سوال",\n'
        '    "option_a": "گزینه A",\n'
        '    "option_b": "گزینه B",\n'
        '    "option_c": "گزینه C",\n'
        '    "option_d": "گزینه D",\n'
        '    "correct_option": "A"\n'
        "  },\n"
        "  ...\n"
        "]\n\n"
        f"متن درس‌نامه:\n{study_material.content_md}"
    )

    conversation = [
        {"role": "system", "content": "You are a helpful quiz generator."},
        {"role": "user", "content": prompt}
    ]

    try:
        quiz_json = chat_completion(conversation)
        quiz_data = extract_json(quiz_json)

        # حذف سوالات قبلی مرتبط با این درس‌نامه (در صورت وجود)
        study_material.quiz_questions.all().delete()

        for q in quiz_data:
            QuizQuestion.objects.create(
                study_material=study_material,
                question_text=q.get('question_text'),
                option_a=q.get('option_a'),
                option_b=q.get('option_b'),
                option_c=q.get('option_c'),
                option_d=q.get('option_d'),
                correct_option=q.get('correct_option')
            )
    except Exception as e:
        print("AI error:", e)
        return render(request, 'app/quize.html', {'error': 'خطا در دریافت سوالات آزمون از هوش مصنوعی.'})

    quiz_questions = study_material.quiz_questions.all()
    total_questions = quiz_questions.count()

    for q in quiz_questions:
        q.options = [q.option_a, q.option_b, q.option_c, q.option_d]

    context = {
        'study_material': study_material,
        'quiz_questions': quiz_questions,
        'total_questions': total_questions,
    }
    return render(request, 'app/quize.html', context)


@login_required(login_url='login')
def submit_quiz_answer(request):
    """
    ویو ثبت پاسخ کاربر برای یک سوال آزمون (از طریق درخواست POST).
    """
    if request.method == 'POST':
        user = request.user
        question_id = request.POST.get('question_id')
        selected_option = request.POST.get('selected_option')

        if not question_id or not selected_option:
            return HttpResponseBadRequest("پارامترهای لازم ارسال نشده‌اند.")

        try:
            question = QuizQuestion.objects.get(id=question_id)
        except QuizQuestion.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'سوال یافت نشد.'})

        record_activity(user)
        answer, created = QuizUserAnswer.objects.update_or_create(
            user=user,
            quiz_question=question,
            defaults={'selected_option': selected_option}
        )
        if created and answer.is_correct:
            award_xp(user, 2)
        # گزینه درست فقط «بعد از پاسخ» از سرور برمی‌گردد (نه داخل HTML صفحه)
        return JsonResponse({
            'success': True,
            'is_correct': answer.is_correct,
            'correct_option': question.correct_option,
        })
    else:
        return HttpResponseBadRequest("روش درخواست نامعتبر است.")

