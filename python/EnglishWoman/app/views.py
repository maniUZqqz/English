from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages as dj_messages
from django.db import models
from .forms import LoginForm, UserResponseForm, RegisterForm
from django.shortcuts import redirect, render, get_object_or_404
import json, re
from django.http import JsonResponse
from .models import Question, UserResponse, UserProfile, UserLevel
from django.utils import timezone
from django.contrib.auth.decorators import login_required
import markdown

from EnglishWoman.services import chat_completion, extract_json
from .usage import QuotaExceeded, consume_ai_quota, current_streak, record_activity, usage_today


def quota_exceeded_page(request, exc):
    """صفحه مشترک «سهمیه امروز تمام شد»."""
    _, limit = usage_today(request.user)
    return render(request, 'app/quota_exceeded.html', {
        'message': str(exc),
        'limit': limit,
    }, status=429)


def _next_session(user):
    """نزدیک‌ترین جلسه از برنامه هفتگی کلاس‌های کاربر (تا ۷ روز آینده)."""
    from datetime import timedelta
    from classroom.models import ClassSchedule
    schedules = ClassSchedule.objects.filter(
        models.Q(classroom__students=user) | models.Q(classroom__teacher=user),
        classroom__is_active=True,
    ).select_related('classroom').distinct()
    if not schedules:
        return None
    now = timezone.localtime()
    best = None
    for schedule in schedules:
        for offset in range(8):
            day = now.date() + timedelta(days=offset)
            if day.weekday() != schedule.weekday:
                continue
            if offset == 0 and schedule.end_time <= now.time():
                continue
            candidate = (day, schedule.start_time, schedule)
            if best is None or candidate[:2] < best[:2]:
                best = candidate
            break
    if not best:
        return None
    return {'date': best[0], 'schedule': best[2]}


def _activity_chart(user, days=14):
    """داده نمودار فعالیت ۱۴ روز اخیر برای داشبورد."""
    from datetime import timedelta
    from .models import DailyActivity
    today = timezone.localdate()
    start = today - timedelta(days=days - 1)
    by_date = {
        a.date: a.ai_requests
        for a in DailyActivity.objects.filter(user=user, date__gte=start)
    }
    labels, values = [], []
    for i in range(days):
        day = start + timedelta(days=i)
        labels.append(day.strftime('%m/%d'))
        values.append(by_date.get(day, 0))
    return {'labels': labels, 'values': values}


def home(request):
    """صفحه اصلی: برای مهمان‌ها لندینگ، برای کاربران واردشده داشبورد."""
    if not request.user.is_authenticated:
        return render(request, 'app/landing.html')

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    level = UserLevel.objects.filter(user=request.user).order_by('-created_at').first()

    # آمار برای داشبورد
    from qqz.models import StudyMaterial, QuizUserAnswer
    from tools.models import SavedWord
    lessons_count = StudyMaterial.objects.filter(user=request.user).count()
    quiz_answers = QuizUserAnswer.objects.filter(user=request.user)
    quiz_total = quiz_answers.count()
    quiz_correct = quiz_answers.filter(is_correct=True).count()
    words = SavedWord.objects.filter(user=request.user)
    words_count = words.count()
    words_due = words.filter(next_review__lte=timezone.localdate()).count()
    used_today, daily_limit = usage_today(request.user)
    classes_count = request.user.enrolled_classes.count() + request.user.teaching_classes.count()

    return render(request, 'app/home.html', {
        'is_teacher': profile.is_teacher,
        'classes_count': classes_count,
        'progress': profile.progress,
        'level': level,
        'lessons_count': lessons_count,
        'quiz_total': quiz_total,
        'quiz_correct': quiz_correct,
        'words_count': words_count,
        'words_due': words_due,
        'streak': current_streak(request.user),
        'used_today': used_today,
        'daily_limit': daily_limit,
        'next_session': _next_session(request.user),
        'chart': _activity_chart(request.user),
    })


def generate_questions(user):
    """
    تولید 10 سوال گرامری برای «همین کاربر» از طریق API.
    در صورت خطا، exception بالا می‌رود تا صفحه خطای شفاف نمایش داده شود
    (به جای سوالات نمونه‌ی بی‌معنی).
    """
    prompt = (
        "Generate 10 multiple choice English grammar questions in JSON format. "
        "Each question should include the following keys: text, option1, option2, option3, option4, correct_option. "
        "The correct_option should be a number between 1 and 4. "
        "Questions should range from beginner to advanced so the test can estimate the learner's level. "
        "Return the result as a JSON array."
    )
    conversation_history = [
        {"role": "system", "content": "You are a question generator for an English grammar placement test."},
        {"role": "user", "content": prompt},
    ]
    generated_text = chat_completion(conversation_history)
    questions_data = extract_json(generated_text)
    if not questions_data:
        raise ValueError('Empty question list from AI')
    for q in questions_data:
        Question.objects.create(
            user=user,
            text=q.get("text", "No question text provided"),
            option1=q.get("option1", "Option A"),
            option2=q.get("option2", "Option B"),
            option3=q.get("option3", "Option C"),
            option4=q.get("option4", "Option D"),
            correct_option=int(q.get("correct_option", 1)),
        )


@login_required(login_url='login')
def level_determination(request):
    # تولید سوالات یک درخواست AI مصرف می‌کند
    try:
        consume_ai_quota(request.user)
    except QuotaExceeded as e:
        return quota_exceeded_page(request, e)
    # شروع آزمون جدید — فقط داده‌های همین کاربر پاک می‌شود
    Question.objects.filter(user=request.user).delete()
    UserResponse.objects.filter(user=request.user).delete()
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.progress = 0
    profile.save()
    try:
        generate_questions(request.user)
    except Exception as e:
        print('generate_questions failed:', e)
        return render(request, 'app/ai_error.html', status=503)
    first_q = Question.objects.filter(user=request.user).order_by('id').first()
    return render(request, 'app/level-determination.html', {
        'question': first_q,
        'question_number': 1,
        'total_questions': 10,
        'progress': 0,
    })


@login_required(login_url='login')
def submit_response(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST allowed'}, status=405)
    form = UserResponseForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': 'Invalid form data'}, status=400)
    qid = form.cleaned_data['question_id']
    sel = form.cleaned_data['selected_option']
    q = get_object_or_404(Question, id=qid, user=request.user)
    record_activity(request.user)
    correct = (sel == q.correct_option)
    # ذخیره پاسخ
    UserResponse.objects.create(
        user=request.user,
        question=q,
        selected_option=sel,
        is_correct=correct,
    )
    # محاسبه‌ی پیشرفت (فقط سوالات همین کاربر)
    user_questions = Question.objects.filter(user=request.user)
    total = user_questions.count()
    correct_count = UserResponse.objects.filter(user=request.user, is_correct=True).count()
    progress = int((correct_count / total) * 100) if total else 0
    # به‌روزرسانی پروفایل
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.progress = progress
    profile.save()
    # پیدا کردن سوال بعدی — فیدبک فوری و محلی (بدون فراخوانی AI برای هر پاسخ)
    nxt = user_questions.filter(id__gt=q.id).order_by('id').first()
    if nxt:
        qnum = user_questions.filter(id__lte=q.id).count() + 1
        return JsonResponse({
            'is_correct': correct,
            'correct_option': q.correct_option,
            'next_question': {
                'id': nxt.id,
                'text': nxt.text,
                'options': [nxt.option1, nxt.option2, nxt.option3, nxt.option4],
                'question_number': qnum,
                'total_questions': total,
                'progress': progress,
            },
            'test_completed': False,
        })
    else:
        return JsonResponse({
            'is_correct': correct,
            'correct_option': q.correct_option,
            'test_completed': True,
            'progress': progress,
        })


@login_required(login_url='login')
def test_completed(request):
    # فقط پاسخ‌های کاربر جاری
    responses = UserResponse.objects.filter(user=request.user).order_by('created_at')
    # ساخت prompt برای تحلیل نهایی
    prompt = (
        "بر اساس پاسخ‌های زیر سطح کاربر را تعیین کن و در قالب Markdown دو بخش 'سطح' و 'توضیحات' بده. "
        "سطح را بر اساس استاندارد CEFR (A1 تا C2) مشخص کن:\n\n"
    )
    for r in responses:
        prompt += f"سوال: {r.question.text}\nپاسخ: Option {r.selected_option} - {'صحیح' if r.is_correct else 'غلط'}\n\n"
    # اگر قبلاً سطح ذخیره شده بود، دستورالعمل تنظیم سختی اضافه کن
    if UserLevel.objects.filter(user=request.user).exists():
        prompt += "این آزمون تکراری است؛ با توجه به نقاط ضعف قبلی، سختی را تنظیم کن."
    conversation = [
        {"role": "system", "content": "You are an English grammar teaching assistant."},
        {"role": "user", "content": prompt},
    ]
    try:
        consume_ai_quota(request.user)
        md = chat_completion(conversation)
    except QuotaExceeded:
        md = "# سطح\nنامشخص\n\n# توضیحات\nسهمیه‌ی روزانه‌ی هوش مصنوعی تمام شده؛ تحلیل فردا در دسترس است."
    except Exception:
        md = "# سطح\nنامشخص\n\n# توضیحات\nتحلیل در دسترس نیست."
    # جدا کردن بخش‌ها
    parts = md.split("# توضیحات")
    level_md = parts[0].replace("# سطح", "").strip()
    expl_md = parts[1].strip() if len(parts) > 1 else ""
    # تبدیل به HTML
    level_html = markdown.markdown(level_md)
    expl_html = markdown.markdown(expl_md)
    # ذخیره یا به‌روزرسانی UserLevel
    ul, created = UserLevel.objects.get_or_create(user=request.user)
    ul.level_title = level_html
    ul.level_explanation = expl_html
    ul.save()
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return render(request, 'app/test_completed.html', {
        'level_title': level_html,
        'level_explanation': expl_html,
        'progress': profile.progress,
    })


def register_view(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()  # فرم خودش set_password و ذخیره را انجام می‌دهد
            login(request, user)  # ورود خودکار
            return redirect("home")
    else:
        form = RegisterForm()
    return render(request, "app/register.html", {"form": form})


LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 600  # ۱۰ دقیقه


def login_view(request):
    from django.core.cache import cache

    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            # محدودیت تلاش ناموفق (ضد brute-force)
            throttle_key = f"login_fail:{username.lower()}"
            fails = cache.get(throttle_key, 0)
            if fails >= LOGIN_MAX_ATTEMPTS:
                form.add_error(None, "تلاش‌های ناموفق زیاد بود — ۱۰ دقیقه بعد دوباره امتحان کنید.")
                return render(request, "app/login.html", {"form": form})
            user = authenticate(username=username, password=password)
            if user:
                cache.delete(throttle_key)
                login(request, user)
                return redirect("home")
            else:
                cache.set(throttle_key, fails + 1, LOGIN_LOCKOUT_SECONDS)
                form.add_error(None, "نام کاربری یا رمز عبور اشتباه است.")
    else:
        form = LoginForm()
    return render(request, "app/login.html", {"form": form})


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required(login_url='login')
def skills_view(request):
    """صفحه ۵ مهارت زبان — برای هر مهارت یک سیستم آموزش."""
    from qqz.models import StudyMaterial, QuizUserAnswer
    from tools.models import SavedWord, WritingSubmission
    user = request.user
    words = SavedWord.objects.filter(user=user)
    writings = WritingSubmission.objects.filter(user=user)
    last_writing = writings.first()
    quiz_answers = QuizUserAnswer.objects.filter(user=user)
    return render(request, 'app/skills.html', {
        'lessons_count': StudyMaterial.objects.filter(user=user).count(),
        'quiz_total': quiz_answers.count(),
        'quiz_correct': quiz_answers.filter(is_correct=True).count(),
        'words_count': words.count(),
        'words_due': words.filter(next_review__lte=timezone.localdate()).count(),
        'writings_count': writings.count(),
        'last_band': last_writing.band if last_writing else None,
        'last_writing_score': last_writing.score if last_writing else None,
    })


@login_required(login_url='login')
def profile_view(request):
    """صفحه پروفایل: اطلاعات حساب، تغییر ایمیل و تغییر رمز عبور."""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    password_form = PasswordChangeForm(request.user)

    if request.method == 'POST':
        if 'change_email' in request.POST:
            email = request.POST.get('email', '').strip()
            if email:
                request.user.email = email
                request.user.save()
                dj_messages.success(request, 'ایمیل به‌روزرسانی شد.')
            else:
                dj_messages.error(request, 'ایمیل را وارد کنید.')
            return redirect('profile')
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)  # کاربر لاگین بماند
                dj_messages.success(request, 'رمز عبور با موفقیت تغییر کرد. ✅')
                return redirect('profile')
            else:
                dj_messages.error(request, 'رمز عبور تغییر نکرد — خطاها را بررسی کنید.')

    level = UserLevel.objects.filter(user=request.user).order_by('-created_at').first()
    return render(request, 'app/profile.html', {
        'profile': profile,
        'level': level,
        'password_form': password_form,
        'streak': current_streak(request.user),
    })
