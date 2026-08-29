"""ویوهای کلاس زبان: کلاس، جلسات و حضورغیاب، تکلیف، آزمون کلاسی، کارنامه و گفتگو."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count, Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import strip_tags

from app.models import UserLevel, UserProfile
from app.usage import QuotaExceeded, consume_ai_quota, current_streak, record_activity
from app.views import quota_exceeded_page
from EnglishWoman.services import AIDisabled, chat_completion, extract_json
from .forms import (AnnouncementForm, AssignmentForm, ClassroomForm, CommentForm,
                    ExamForm, ExamQuestionForm, GradeForm, JoinClassForm,
                    ScheduleForm, SessionForm, SubmissionForm)
from .models import (Attendance, Assignment, ClassExam, ClassSession,
                     Classroom, ExamAnswer, ExamAttempt, Submission)


def _profile(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return profile


def teacher_required(view_func):
    """فقط کاربرانی که در ادمین نقش «معلم» گرفته‌اند."""
    @wraps(view_func)
    @login_required(login_url='login')
    def wrapper(request, *args, **kwargs):
        if not _profile(request.user).is_teacher:
            return HttpResponseForbidden('برای این کار نقش معلم لازم است (از پنل ادمین تنظیم می‌شود).')
        return view_func(request, *args, **kwargs)
    return wrapper


def _can_view_class(user, classroom):
    return classroom.teacher_id == user.id or classroom.students.filter(id=user.id).exists()


# ---------- کلاس‌ها ----------

@login_required(login_url='login')
def my_classes(request):
    profile = _profile(request.user)
    teaching = Classroom.objects.filter(teacher=request.user).annotate(
        student_count=Count('students', distinct=True),
    )
    enrolled = request.user.enrolled_classes.filter(is_active=True).select_related('teacher')
    return render(request, 'classroom/my_classes.html', {
        'is_teacher': profile.is_teacher,
        'teaching': teaching,
        'enrolled': enrolled,
        'join_form': JoinClassForm(),
    })


@login_required(login_url='login')
def join_class(request):
    if request.method != 'POST':
        return redirect('my_classes')
    form = JoinClassForm(request.POST)
    if form.is_valid():
        code = form.cleaned_data['join_code']
        classroom = Classroom.objects.filter(join_code=code, is_active=True).first()
        if not classroom:
            messages.error(request, 'کلاسی با این کد پیدا نشد.')
        elif classroom.teacher_id == request.user.id:
            messages.error(request, 'شما معلم این کلاس هستید و نیازی به عضویت ندارید.')
        elif classroom.students.filter(id=request.user.id).exists():
            messages.info(request, f'شما از قبل عضو «{classroom.name}» هستید.')
        else:
            classroom.students.add(request.user)
            record_activity(request.user)
            messages.success(request, f'به کلاس «{classroom.name}» خوش آمدید! 🎉')
            return redirect('class_detail', pk=classroom.pk)
    else:
        messages.error(request, 'کد کلاس را وارد کنید.')
    return redirect('my_classes')


@login_required(login_url='login')
def leave_class(request, pk):
    if request.method != 'POST':
        return redirect('my_classes')
    classroom = get_object_or_404(Classroom, pk=pk)
    classroom.students.remove(request.user)
    messages.info(request, f'از کلاس «{classroom.name}» خارج شدید.')
    return redirect('my_classes')


@teacher_required
def create_class(request):
    if request.method == 'POST':
        form = ClassroomForm(request.POST)
        if form.is_valid():
            classroom = form.save(commit=False)
            classroom.teacher = request.user
            classroom.save()
            messages.success(request, f'کلاس «{classroom.name}» ساخته شد. کد عضویت: {classroom.join_code}')
            return redirect('class_detail', pk=classroom.pk)
    else:
        form = ClassroomForm()
    return render(request, 'classroom/create_class.html', {'form': form})


@login_required(login_url='login')
def class_detail(request, pk):
    classroom = get_object_or_404(Classroom, pk=pk)
    if not _can_view_class(request.user, classroom):
        return HttpResponseForbidden('شما عضو این کلاس نیستید.')

    is_teacher = classroom.teacher_id == request.user.id
    announcements = classroom.announcements.all()[:20]
    assignments = classroom.assignments.all()
    schedules = classroom.schedules.all()
    sessions = classroom.sessions.all()[:12]
    exams = classroom.exams.all() if is_teacher else classroom.exams.filter(is_published=True)

    context = {
        'classroom': classroom,
        'is_teacher': is_teacher,
        'announcements': announcements,
        'schedules': schedules,
        'sessions': sessions,
    }

    if is_teacher:
        # گزارش پیشرفت زبان‌آموزها — با کوئری‌های bulk (بدون N+1)
        from app.usage import current_streaks
        students = list(
            classroom.students.select_related('userlevel', 'userprofile').annotate(
                quiz_total=Count('quizuseranswer', distinct=True),
                quiz_correct=Count('quizuseranswer',
                                   filter=Q(quizuseranswer__is_correct=True), distinct=True),
                grade_avg=Avg('submissions__grade',
                              filter=Q(submissions__assignment__classroom=classroom)),
            )
        )
        streaks = current_streaks([s.id for s in students])
        student_rows = []
        for student in students:
            level = getattr(student, 'userlevel', None)
            profile = getattr(student, 'userprofile', None)
            student_rows.append({
                'user': student,
                'level': strip_tags(level.level_title).strip() if level else '—',
                'progress': profile.progress if profile else 0,
                'streak': streaks.get(student.id, 0),
                'quiz_total': student.quiz_total,
                'quiz_correct': student.quiz_correct,
                'grade_avg': round(student.grade_avg) if student.grade_avg is not None else None,
            })
        assignment_rows = [{
            'assignment': a,
            'submitted_count': a.submissions.count(),
            'graded_count': a.submissions.filter(grade__isnull=False).count(),
        } for a in assignments]
        exam_rows = [{
            'exam': e,
            'question_count': e.questions.count(),
            'attempt_count': e.attempts.count(),
        } for e in exams]
        context.update({
            'student_rows': student_rows,
            'assignment_rows': assignment_rows,
            'exam_rows': exam_rows,
            'announcement_form': AnnouncementForm(),
            'assignment_form': AssignmentForm(),
            'session_form': SessionForm(),
            'schedule_form': ScheduleForm(),
        })
    else:
        my_submissions = {
            s.assignment_id: s
            for s in Submission.objects.filter(student=request.user, assignment__classroom=classroom)
        }
        assignment_rows = [{
            'assignment': a,
            'submission': my_submissions.get(a.id),
        } for a in assignments]
        my_attempts = {a.exam_id: a for a in ExamAttempt.objects.filter(
            student=request.user, exam__classroom=classroom)}
        exam_rows = [{
            'exam': e,
            'attempt': my_attempts.get(e.id),
        } for e in exams]
        context.update({
            'assignment_rows': assignment_rows,
            'exam_rows': exam_rows,
        })

    return render(request, 'classroom/class_detail.html', context)


# ---------- اطلاعیه و تکلیف ----------

@teacher_required
def add_announcement(request, pk):
    classroom = get_object_or_404(Classroom, pk=pk, teacher=request.user)
    if request.method == 'POST':
        form = AnnouncementForm(request.POST)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.classroom = classroom
            announcement.save()
            messages.success(request, 'اطلاعیه منتشر شد.')
        else:
            messages.error(request, 'عنوان و متن اطلاعیه را کامل کنید.')
    return redirect('class_detail', pk=pk)


@teacher_required
def add_assignment(request, pk):
    classroom = get_object_or_404(Classroom, pk=pk, teacher=request.user)
    if request.method == 'POST':
        form = AssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.classroom = classroom
            assignment.save()
            messages.success(request, f'تکلیف «{assignment.title}» ساخته شد.')
        else:
            messages.error(request, 'عنوان و توضیح تکلیف را کامل کنید.')
    return redirect('class_detail', pk=pk)


@login_required(login_url='login')
def assignment_detail(request, pk):
    assignment = get_object_or_404(Assignment.objects.select_related('classroom'), pk=pk)
    classroom = assignment.classroom
    if not _can_view_class(request.user, classroom):
        return HttpResponseForbidden('شما عضو این کلاس نیستید.')

    is_teacher = classroom.teacher_id == request.user.id
    context = {
        'assignment': assignment,
        'classroom': classroom,
        'is_teacher': is_teacher,
        'comments': assignment.comments.select_related('author'),
        'comment_form': CommentForm(),
    }

    if is_teacher:
        submissions = assignment.submissions.select_related('student')
        context['submission_rows'] = [
            {'submission': s, 'grade_form': GradeForm(instance=s, prefix=str(s.pk))}
            for s in submissions
        ]
        submitted_ids = submissions.values_list('student_id', flat=True)
        context['missing_students'] = classroom.students.exclude(id__in=submitted_ids)
    else:
        submission = Submission.objects.filter(assignment=assignment, student=request.user).first()
        context['submission'] = submission
        context['submission_form'] = SubmissionForm(instance=submission)

    return render(request, 'classroom/assignment_detail.html', context)


@login_required(login_url='login')
def submit_assignment(request, pk):
    assignment = get_object_or_404(Assignment.objects.select_related('classroom'), pk=pk)
    classroom = assignment.classroom
    if not classroom.students.filter(id=request.user.id).exists():
        return HttpResponseForbidden('فقط زبان‌آموزهای عضو کلاس می‌توانند تکلیف تحویل دهند.')
    if request.method == 'POST':
        if assignment.is_past_due:
            messages.error(request, 'مهلت تحویل این تکلیف گذشته است.')
            return redirect('assignment_detail', pk=pk)
        submission = Submission.objects.filter(assignment=assignment, student=request.user).first()
        if submission and submission.is_graded:
            messages.error(request, 'این تکلیف نمره گرفته و دیگر قابل ویرایش نیست.')
            return redirect('assignment_detail', pk=pk)
        form = SubmissionForm(request.POST, request.FILES, instance=submission)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.assignment = assignment
            obj.student = request.user
            obj.save()
            record_activity(request.user)
            messages.success(request, 'تکلیف شما ثبت شد. ✅')
        else:
            for errs in form.errors.values():
                for e in errs:
                    messages.error(request, e)
    return redirect('assignment_detail', pk=pk)


@teacher_required
def grade_submission(request, pk):
    submission = get_object_or_404(
        Submission.objects.select_related('assignment__classroom'), pk=pk,
        assignment__classroom__teacher=request.user,
    )
    if request.method == 'POST':
        form = GradeForm(request.POST, instance=submission, prefix=str(submission.pk))
        if form.is_valid():
            form.save()
            messages.success(request, f'نمره {submission.student.username} ثبت شد.')
        else:
            messages.error(request, 'نمره باید بین ۰ تا ۱۰۰ باشد.')
    return redirect('assignment_detail', pk=submission.assignment_id)


@login_required(login_url='login')
def add_comment(request, pk):
    """گفتگوی زیر تکلیف — برای همه اعضای کلاس."""
    assignment = get_object_or_404(Assignment.objects.select_related('classroom'), pk=pk)
    if not _can_view_class(request.user, assignment.classroom):
        return HttpResponseForbidden('شما عضو این کلاس نیستید.')
    if request.method == 'POST':
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.assignment = assignment
            comment.author = request.user
            comment.save()
            record_activity(request.user)
        else:
            messages.error(request, 'متن نظر را بنویسید.')
    return redirect('assignment_detail', pk=pk)


@teacher_required
def remove_student(request, pk, student_id):
    classroom = get_object_or_404(Classroom, pk=pk, teacher=request.user)
    if request.method == 'POST':
        classroom.students.remove(student_id)
        messages.info(request, 'زبان‌آموز از کلاس حذف شد.')
    return redirect('class_detail', pk=pk)


# ---------- برنامه هفتگی و جلسات ----------

@teacher_required
def add_schedule(request, pk):
    classroom = get_object_or_404(Classroom, pk=pk, teacher=request.user)
    if request.method == 'POST':
        form = ScheduleForm(request.POST)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.classroom = classroom
            schedule.save()
            messages.success(request, 'برنامه هفتگی اضافه شد.')
        else:
            messages.error(request, 'روز و ساعت را کامل وارد کنید.')
    return redirect('class_detail', pk=pk)


@teacher_required
def delete_schedule(request, pk, schedule_id):
    classroom = get_object_or_404(Classroom, pk=pk, teacher=request.user)
    if request.method == 'POST':
        classroom.schedules.filter(pk=schedule_id).delete()
    return redirect('class_detail', pk=pk)


@teacher_required
def add_session(request, pk):
    classroom = get_object_or_404(Classroom, pk=pk, teacher=request.user)
    if request.method == 'POST':
        form = SessionForm(request.POST)
        if form.is_valid():
            if classroom.sessions.filter(date=form.cleaned_data['date']).exists():
                messages.error(request, 'برای این تاریخ قبلاً جلسه ثبت شده است.')
                return redirect('class_detail', pk=pk)
            session = form.save(commit=False)
            session.classroom = classroom
            session.save()
            return redirect('session_detail', pk=session.pk)
        messages.error(request, 'تاریخ جلسه را وارد کنید.')
    return redirect('class_detail', pk=pk)


@teacher_required
def session_detail(request, pk):
    """صفحه حضور و غیاب یک جلسه."""
    session = get_object_or_404(
        ClassSession.objects.select_related('classroom'), pk=pk,
        classroom__teacher=request.user,
    )
    students = session.classroom.students.all()

    if request.method == 'POST':
        for student in students:
            status = request.POST.get(f'status_{student.id}')
            if status in dict(Attendance.STATUS_CHOICES):
                Attendance.objects.update_or_create(
                    session=session, student=student, defaults={'status': status},
                )
        messages.success(request, 'حضور و غیاب ذخیره شد. ✅')
        return redirect('class_detail', pk=session.classroom_id)

    existing = {a.student_id: a.status for a in session.attendances.all()}
    rows = [{'student': s, 'status': existing.get(s.id, 'present')} for s in students]
    return render(request, 'classroom/session_detail.html', {
        'session': session,
        'classroom': session.classroom,
        'rows': rows,
        'status_choices': Attendance.STATUS_CHOICES,
    })


# ---------- آزمون کلاسی ----------

@teacher_required
def create_exam(request, pk):
    classroom = get_object_or_404(Classroom, pk=pk, teacher=request.user)
    if request.method == 'POST':
        form = ExamForm(request.POST)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.classroom = classroom
            exam.save()
            messages.success(request, f'آزمون «{exam.title}» ساخته شد — حالا سوال اضافه کنید.')
            return redirect('exam_detail', pk=exam.pk)
    else:
        form = ExamForm()
    return render(request, 'classroom/create_exam.html', {'form': form, 'classroom': classroom})


@login_required(login_url='login')
def exam_detail(request, pk):
    exam = get_object_or_404(ClassExam.objects.select_related('classroom'), pk=pk)
    classroom = exam.classroom
    if not _can_view_class(request.user, classroom):
        return HttpResponseForbidden('شما عضو این کلاس نیستید.')

    is_teacher = classroom.teacher_id == request.user.id
    questions = exam.questions.all()

    if is_teacher:
        attempts = exam.attempts.select_related('student').order_by('-score')
        return render(request, 'classroom/exam_teacher.html', {
            'exam': exam,
            'classroom': classroom,
            'questions': questions,
            'attempts': attempts,
            'question_form': ExamQuestionForm(),
        })

    # زبان‌آموز
    if not exam.is_published:
        return HttpResponseForbidden('این آزمون هنوز منتشر نشده است.')
    attempt = ExamAttempt.objects.filter(exam=exam, student=request.user).first()
    if attempt and attempt.finished_at:
        # نمایش کارنامه‌ی این آزمون
        answers = {a.question_id: a for a in attempt.answers.all()}
        rows = [{'question': q, 'answer': answers.get(q.id)} for q in questions]
        return render(request, 'classroom/exam_result.html', {
            'exam': exam, 'classroom': classroom, 'attempt': attempt, 'rows': rows,
        })
    if attempt:
        # آزمونِ در جریان — زمان باقی‌مانده از سرور محاسبه می‌شود (رفرش تایمر را ریست نمی‌کند)
        elapsed = (timezone.now() - attempt.started_at).total_seconds()
        remaining = max(0, int(exam.duration_minutes * 60 - elapsed))
        return render(request, 'classroom/exam_take.html', {
            'exam': exam, 'classroom': classroom, 'questions': questions,
            'remaining_seconds': remaining,
        })
    # هنوز شروع نکرده — صفحه معرفی با دکمه شروع
    return render(request, 'classroom/exam_intro.html', {
        'exam': exam, 'classroom': classroom, 'question_count': questions.count(),
    })


@login_required(login_url='login')
def start_exam(request, pk):
    """شروع رسمی آزمون — زمان شروع سمت سرور ثبت می‌شود."""
    exam = get_object_or_404(ClassExam.objects.select_related('classroom'), pk=pk, is_published=True)
    if not exam.classroom.students.filter(id=request.user.id).exists():
        return HttpResponseForbidden('فقط زبان‌آموزهای عضو کلاس می‌توانند در آزمون شرکت کنند.')
    if request.method == 'POST':
        ExamAttempt.objects.get_or_create(exam=exam, student=request.user)
    return redirect('exam_detail', pk=pk)


@teacher_required
def add_exam_question(request, pk):
    exam = get_object_or_404(ClassExam, pk=pk, classroom__teacher=request.user)
    if request.method == 'POST':
        form = ExamQuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.exam = exam
            question.save()
            messages.success(request, 'سوال اضافه شد.')
        else:
            messages.error(request, 'همه فیلدهای سوال را کامل کنید.')
    return redirect('exam_detail', pk=pk)


@teacher_required
def delete_exam_question(request, pk, question_id):
    exam = get_object_or_404(ClassExam, pk=pk, classroom__teacher=request.user)
    if request.method == 'POST':
        exam.questions.filter(pk=question_id).delete()
    return redirect('exam_detail', pk=pk)


@teacher_required
def ai_exam_questions(request, pk):
    """تولید ۵ سوال با هوش مصنوعی بر اساس موضوعی که معلم می‌دهد."""
    exam = get_object_or_404(ClassExam, pk=pk, classroom__teacher=request.user)
    if request.method != 'POST':
        return redirect('exam_detail', pk=pk)
    topic = request.POST.get('topic', '').strip()[:200]
    if not topic:
        messages.error(request, 'موضوع سوالات را وارد کنید.')
        return redirect('exam_detail', pk=pk)
    try:
        consume_ai_quota(request.user)
    except QuotaExceeded as e:
        return quota_exceeded_page(request, e)
    prompt = (
        f"Create 5 multiple-choice English questions about '{topic}' "
        f"for {exam.classroom.get_level_display()} level students. "
        'Return ONLY a JSON array like: '
        '[{"text": "...", "option_a": "...", "option_b": "...", "option_c": "...", '
        '"option_d": "...", "correct_option": "A"}]'
    )
    try:
        reply = chat_completion([
            {'role': 'system', 'content': 'You are an English exam generator.'},
            {'role': 'user', 'content': prompt},
        ])
        data = extract_json(reply)
        created = 0
        for q in data:
            if not q.get('text'):
                continue
            exam.questions.create(
                text=q.get('text'),
                option_a=q.get('option_a', 'A'),
                option_b=q.get('option_b', 'B'),
                option_c=q.get('option_c', 'C'),
                option_d=q.get('option_d', 'D'),
                correct_option=(q.get('correct_option') or 'A')[:1].upper(),
            )
            created += 1
        messages.success(request, f'{created} سوال با هوش مصنوعی ساخته شد — قبل از انتشار بازبینی کنید.')
    except AIDisabled:
        messages.error(request, 'هوش مصنوعی هنوز راه‌اندازی نشده — کلید API را در پنل ادمین وارد کنید.')
    except Exception as e:
        print('ai_exam_questions error:', e)
        messages.error(request, 'خطا در تولید سوالات. دوباره تلاش کنید.')
    return redirect('exam_detail', pk=pk)


@teacher_required
def publish_exam(request, pk):
    exam = get_object_or_404(ClassExam, pk=pk, classroom__teacher=request.user)
    if request.method == 'POST':
        if not exam.is_published and not exam.questions.exists():
            messages.error(request, 'آزمون بدون سوال را نمی‌توان منتشر کرد.')
        else:
            exam.is_published = not exam.is_published
            exam.save()
            messages.success(request, 'آزمون منتشر شد. ✅' if exam.is_published else 'آزمون از انتشار خارج شد.')
    return redirect('exam_detail', pk=pk)


@login_required(login_url='login')
def take_exam(request, pk):
    exam = get_object_or_404(ClassExam.objects.select_related('classroom'), pk=pk, is_published=True)
    classroom = exam.classroom
    if not classroom.students.filter(id=request.user.id).exists():
        return HttpResponseForbidden('فقط زبان‌آموزهای عضو کلاس می‌توانند در آزمون شرکت کنند.')
    if request.method != 'POST':
        return redirect('exam_detail', pk=pk)

    attempt = ExamAttempt.objects.filter(exam=exam, student=request.user).first()
    if attempt is None:
        messages.error(request, 'اول باید آزمون را شروع کنید.')
        return redirect('exam_detail', pk=pk)
    if attempt.finished_at:
        messages.error(request, 'شما قبلاً در این آزمون شرکت کرده‌اید.')
        return redirect('exam_detail', pk=pk)

    questions = list(exam.questions.all())
    # کنترل زمان سمت سرور: مهلت + ۶۰ ثانیه ارفاق شبکه
    elapsed = (timezone.now() - attempt.started_at).total_seconds()
    out_of_time = elapsed > exam.duration_minutes * 60 + 60

    correct = 0
    for q in questions:
        selected = '' if out_of_time else (request.POST.get(f'q_{q.id}') or '').upper()[:1]
        is_correct = selected == q.correct_option
        if is_correct:
            correct += 1
        ExamAnswer.objects.create(
            attempt=attempt, question=q, selected=selected, is_correct=is_correct,
        )
    attempt.score = round(correct / len(questions) * 100) if questions else 0
    attempt.finished_at = timezone.now()
    attempt.save()
    record_activity(request.user)
    if out_of_time:
        messages.error(request, 'پاسخ‌ها بعد از پایان زمان رسید و ثبت نشد — نمره: ۰')
    else:
        messages.success(request, f'آزمون ثبت شد — نمره شما: {attempt.score} از ۱۰۰')
    return redirect('exam_detail', pk=pk)


# ---------- کارنامه ----------

@login_required(login_url='login')
def report_card(request, pk, student_id=None):
    classroom = get_object_or_404(Classroom, pk=pk)
    is_teacher = classroom.teacher_id == request.user.id

    if student_id is None:
        student = request.user
        if not is_teacher and not classroom.students.filter(id=student.id).exists():
            return HttpResponseForbidden('شما عضو این کلاس نیستید.')
    else:
        if not is_teacher:
            return HttpResponseForbidden('فقط معلم می‌تواند کارنامه دیگران را ببیند.')
        student = get_object_or_404(classroom.students, id=student_id)

    # حضور و غیاب
    total_sessions = classroom.sessions.count()
    attendance_qs = Attendance.objects.filter(session__classroom=classroom, student=student)
    att_counts = {status: 0 for status, _ in Attendance.STATUS_CHOICES}
    for a in attendance_qs:
        att_counts[a.status] += 1
    attended = att_counts['present'] + att_counts['late']
    attendance_percent = round(attended / total_sessions * 100) if total_sessions else None

    # تکالیف
    submissions = {
        s.assignment_id: s
        for s in Submission.objects.filter(student=student, assignment__classroom=classroom)
    }
    assignment_rows = [{
        'assignment': a,
        'submission': submissions.get(a.id),
    } for a in classroom.assignments.all()]
    grades = [s.grade for s in submissions.values() if s.grade is not None]
    assignment_avg = round(sum(grades) / len(grades)) if grades else None

    # آزمون‌ها
    attempts = {
        a.exam_id: a
        for a in ExamAttempt.objects.filter(student=student, exam__classroom=classroom)
    }
    exam_rows = [{
        'exam': e,
        'attempt': attempts.get(e.id),
    } for e in classroom.exams.filter(is_published=True)]
    scores = [a.score for a in attempts.values() if a.score is not None]
    exam_avg = round(sum(scores) / len(scores)) if scores else None

    parts = [v for v in (assignment_avg, exam_avg) if v is not None]
    overall = round(sum(parts) / len(parts)) if parts else None

    level = UserLevel.objects.filter(user=student).order_by('-created_at').first()

    return render(request, 'classroom/report_card.html', {
        'classroom': classroom,
        'student': student,
        'is_teacher': is_teacher,
        'level': strip_tags(level.level_title).strip() if level else '—',
        'streak': current_streak(student),
        'total_sessions': total_sessions,
        'att_counts': att_counts,
        'attendance_percent': attendance_percent,
        'assignment_rows': assignment_rows,
        'assignment_avg': assignment_avg,
        'exam_rows': exam_rows,
        'exam_avg': exam_avg,
        'overall': overall,
    })
