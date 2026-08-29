"""تست‌های کلاس زبان: نقش‌ها، عضویت با کد، تکلیف، تحویل و نمره‌دهی — بدون هیچ فراخوانی AI."""

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from app.models import UserProfile
from .models import Assignment, Classroom, Submission


def make_teacher(username):
    user = User.objects.create_user(username, password='pass12345')
    profile = UserProfile.objects.get(user=user)
    profile.role = 'teacher'
    profile.save()
    return user


class RoleTests(TestCase):
    def test_student_cannot_create_class(self):
        User.objects.create_user('student1', password='pass12345')
        self.client.login(username='student1', password='pass12345')
        response = self.client.get(reverse('create_class'))
        self.assertEqual(response.status_code, 403)

    def test_teacher_can_create_class_with_join_code(self):
        make_teacher('teacher1')
        self.client.login(username='teacher1', password='pass12345')
        response = self.client.post(reverse('create_class'), {
            'name': 'English B1', 'level': 'B1', 'description': 'Evening class',
        })
        classroom = Classroom.objects.get(name='English B1')
        self.assertRedirects(response, reverse('class_detail', args=[classroom.pk]))
        self.assertEqual(len(classroom.join_code), 6)


class JoinTests(TestCase):
    def setUp(self):
        self.teacher = make_teacher('teach')
        self.classroom = Classroom.objects.create(name='C1', teacher=self.teacher)
        self.student = User.objects.create_user('stud', password='pass12345')
        self.client.login(username='stud', password='pass12345')

    def test_join_with_valid_code(self):
        response = self.client.post(reverse('join_class'), {'join_code': self.classroom.join_code})
        self.assertRedirects(response, reverse('class_detail', args=[self.classroom.pk]))
        self.assertTrue(self.classroom.students.filter(id=self.student.id).exists())

    def test_join_with_invalid_code_shows_error(self):
        response = self.client.post(reverse('join_class'), {'join_code': 'WRONG1'}, follow=True)
        self.assertContains(response, 'کلاسی با این کد پیدا نشد')
        self.assertFalse(self.classroom.students.exists())

    def test_non_member_cannot_view_class(self):
        response = self.client.get(reverse('class_detail', args=[self.classroom.pk]))
        self.assertEqual(response.status_code, 403)

    def test_member_and_teacher_can_view_class(self):
        self.classroom.students.add(self.student)
        self.assertEqual(
            self.client.get(reverse('class_detail', args=[self.classroom.pk])).status_code, 200)
        self.client.login(username='teach', password='pass12345')
        self.assertEqual(
            self.client.get(reverse('class_detail', args=[self.classroom.pk])).status_code, 200)


class AssignmentFlowTests(TestCase):
    def setUp(self):
        self.teacher = make_teacher('teach')
        self.classroom = Classroom.objects.create(name='C1', teacher=self.teacher)
        self.student = User.objects.create_user('stud', password='pass12345')
        self.classroom.students.add(self.student)
        self.assignment = Assignment.objects.create(
            classroom=self.classroom, title='Essay 1', description='Write 100 words about your day.',
        )

    def test_student_submits_and_updates(self):
        self.client.login(username='stud', password='pass12345')
        url = reverse('submit_assignment', args=[self.assignment.pk])
        self.client.post(url, {'text': 'My first draft.'})
        self.client.post(url, {'text': 'My improved draft.'})
        submission = Submission.objects.get(assignment=self.assignment, student=self.student)
        self.assertEqual(submission.text, 'My improved draft.')
        self.assertEqual(Submission.objects.count(), 1)

    def test_outsider_cannot_submit(self):
        User.objects.create_user('outsider', password='pass12345')
        self.client.login(username='outsider', password='pass12345')
        response = self.client.post(
            reverse('submit_assignment', args=[self.assignment.pk]), {'text': 'hack'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Submission.objects.exists())

    def test_teacher_grades_and_student_sees_grade(self):
        submission = Submission.objects.create(
            assignment=self.assignment, student=self.student, text='Done.')
        self.client.login(username='teach', password='pass12345')
        self.client.post(reverse('grade_submission', args=[submission.pk]), {
            f'{submission.pk}-grade': 85, f'{submission.pk}-feedback': 'Well done!',
        })
        submission.refresh_from_db()
        self.assertEqual(submission.grade, 85)

        self.client.login(username='stud', password='pass12345')
        page = self.client.get(reverse('assignment_detail', args=[self.assignment.pk]))
        self.assertContains(page, '85/۱۰۰')
        self.assertContains(page, 'Well done!')

    def test_graded_submission_cannot_be_edited(self):
        Submission.objects.create(
            assignment=self.assignment, student=self.student, text='Original.', grade=90)
        self.client.login(username='stud', password='pass12345')
        self.client.post(reverse('submit_assignment', args=[self.assignment.pk]), {'text': 'Changed!'})
        submission = Submission.objects.get(assignment=self.assignment, student=self.student)
        self.assertEqual(submission.text, 'Original.')

    def test_submit_after_due_date_rejected(self):
        from datetime import timedelta
        from django.utils import timezone
        self.assignment.due_date = timezone.now() - timedelta(hours=1)
        self.assignment.save()
        self.client.login(username='stud', password='pass12345')
        self.client.post(reverse('submit_assignment', args=[self.assignment.pk]), {'text': 'Late!'})
        self.assertFalse(Submission.objects.filter(assignment=self.assignment).exists())

    def test_disallowed_file_extension_rejected(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.login(username='stud', password='pass12345')
        bad_file = SimpleUploadedFile('virus.exe', b'MZ...', content_type='application/octet-stream')
        self.client.post(reverse('submit_assignment', args=[self.assignment.pk]),
                         {'text': 'with file', 'file': bad_file})
        self.assertFalse(Submission.objects.filter(assignment=self.assignment).exists())

    def test_other_teacher_cannot_grade(self):
        submission = Submission.objects.create(
            assignment=self.assignment, student=self.student, text='Done.')
        make_teacher('other_teacher')
        self.client.login(username='other_teacher', password='pass12345')
        response = self.client.post(reverse('grade_submission', args=[submission.pk]), {
            f'{submission.pk}-grade': 1,
        })
        self.assertEqual(response.status_code, 404)
        submission.refresh_from_db()
        self.assertIsNone(submission.grade)


class ExamFlowTests(TestCase):
    """جریان کامل آزمون کلاسی: ساخت → سوال → انتشار → شرکت → نمره."""

    def setUp(self):
        self.teacher = make_teacher('examteach')
        self.classroom = Classroom.objects.create(name='C1', teacher=self.teacher)
        self.student = User.objects.create_user('examstud', password='pass12345')
        self.classroom.students.add(self.student)

    def _make_exam(self, published=True, questions=2):
        from .models import ClassExam, ExamQuestion
        exam = ClassExam.objects.create(
            classroom=self.classroom, title='Midterm', is_published=published)
        for i in range(questions):
            ExamQuestion.objects.create(
                exam=exam, text=f'Q{i}?', option_a='a', option_b='b',
                option_c='c', option_d='d', correct_option='A')
        return exam

    def test_teacher_creates_and_publishes_exam(self):
        self.client.login(username='examteach', password='pass12345')
        self.client.post(reverse('create_exam', args=[self.classroom.pk]), {
            'title': 'Final', 'description': '', 'duration_minutes': 20,
        })
        from .models import ClassExam
        exam = ClassExam.objects.get(title='Final')
        # آزمون بدون سوال منتشر نمی‌شود
        self.client.post(reverse('publish_exam', args=[exam.pk]))
        exam.refresh_from_db()
        self.assertFalse(exam.is_published)
        # با سوال منتشر می‌شود
        self.client.post(reverse('add_exam_question', args=[exam.pk]), {
            'text': 'Pick A', 'option_a': 'a', 'option_b': 'b',
            'option_c': 'c', 'option_d': 'd', 'correct_option': 'A',
        })
        self.client.post(reverse('publish_exam', args=[exam.pk]))
        exam.refresh_from_db()
        self.assertTrue(exam.is_published)

    def test_student_takes_exam_and_gets_score(self):
        from .models import ExamAttempt
        exam = self._make_exam(questions=2)
        self.client.login(username='examstud', password='pass12345')
        questions = list(exam.questions.all())
        # بدون «شروع»، ارسال پاسخ پذیرفته نمی‌شود
        self.client.post(reverse('take_exam', args=[exam.pk]), {f'q_{questions[0].id}': 'A'})
        self.assertFalse(ExamAttempt.objects.filter(exam=exam).exists())
        # شروع رسمی (زمان سمت سرور ثبت می‌شود)
        self.client.post(reverse('start_exam', args=[exam.pk]))
        self.assertTrue(ExamAttempt.objects.filter(exam=exam, finished_at=None).exists())
        # ارسال پاسخ‌ها
        self.client.post(reverse('take_exam', args=[exam.pk]), {
            f'q_{questions[0].id}': 'A',  # درست
            f'q_{questions[1].id}': 'B',  # غلط
        })
        attempt = ExamAttempt.objects.get(exam=exam, student=self.student)
        self.assertEqual(attempt.score, 50)
        # شرکت دوباره ممکن نیست
        self.client.post(reverse('take_exam', args=[exam.pk]), {
            f'q_{questions[0].id}': 'A', f'q_{questions[1].id}': 'A',
        })
        self.assertEqual(ExamAttempt.objects.filter(exam=exam).count(), 1)
        # صفحه نتیجه نمره را نشان می‌دهد
        page = self.client.get(reverse('exam_detail', args=[exam.pk]))
        self.assertContains(page, '50')

    def test_answers_after_time_limit_score_zero(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import ExamAttempt
        exam = self._make_exam(questions=1)
        self.client.login(username='examstud', password='pass12345')
        self.client.post(reverse('start_exam', args=[exam.pk]))
        # زمان شروع را به گذشته ببریم (فراتر از مهلت + ارفاق)
        attempt = ExamAttempt.objects.get(exam=exam, student=self.student)
        ExamAttempt.objects.filter(pk=attempt.pk).update(
            started_at=timezone.now() - timedelta(minutes=exam.duration_minutes + 5))
        question = exam.questions.first()
        self.client.post(reverse('take_exam', args=[exam.pk]), {f'q_{question.id}': 'A'})
        attempt.refresh_from_db()
        self.assertEqual(attempt.score, 0)

    def test_exam_intro_shown_before_start_and_timer_survives_refresh(self):
        exam = self._make_exam(questions=1)
        self.client.login(username='examstud', password='pass12345')
        # قبل از شروع: صفحه معرفی
        page = self.client.get(reverse('exam_detail', args=[exam.pk]))
        self.assertTemplateUsed(page, 'classroom/exam_intro.html')
        # بعد از شروع: صفحه آزمون با زمان باقی‌مانده از سرور
        self.client.post(reverse('start_exam', args=[exam.pk]))
        page = self.client.get(reverse('exam_detail', args=[exam.pk]))
        self.assertTemplateUsed(page, 'classroom/exam_take.html')
        self.assertLessEqual(page.context['remaining_seconds'], exam.duration_minutes * 60)

    def test_unpublished_exam_hidden_from_student(self):
        exam = self._make_exam(published=False)
        self.client.login(username='examstud', password='pass12345')
        response = self.client.get(reverse('exam_detail', args=[exam.pk]))
        self.assertEqual(response.status_code, 403)


class AttendanceTests(TestCase):
    """جلسات و حضور و غیاب + بازتاب در کارنامه."""

    def setUp(self):
        self.teacher = make_teacher('attteach')
        self.classroom = Classroom.objects.create(name='C1', teacher=self.teacher)
        self.student = User.objects.create_user('attstud', password='pass12345')
        self.classroom.students.add(self.student)

    def test_teacher_marks_attendance_and_report_card_shows_it(self):
        from .models import Attendance, ClassSession
        self.client.login(username='attteach', password='pass12345')
        # ثبت جلسه
        self.client.post(reverse('add_session', args=[self.classroom.pk]), {
            'date': '2026-08-29', 'topic': 'Unit 1',
        })
        session = ClassSession.objects.get(classroom=self.classroom)
        # ثبت حضور
        self.client.post(reverse('session_detail', args=[session.pk]), {
            f'status_{self.student.id}': 'absent',
        })
        att = Attendance.objects.get(session=session, student=self.student)
        self.assertEqual(att.status, 'absent')
        # کارنامه از نگاه معلم
        page = self.client.get(reverse('report_card', args=[self.classroom.pk, self.student.pk]))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'حضور و غیاب')

    def test_student_sees_own_report_card_only(self):
        self.client.login(username='attstud', password='pass12345')
        page = self.client.get(reverse('my_report_card', args=[self.classroom.pk]))
        self.assertEqual(page.status_code, 200)
        # کارنامه دیگران ممنوع
        other = User.objects.create_user('other2', password='pass12345')
        self.classroom.students.add(other)
        page = self.client.get(reverse('report_card', args=[self.classroom.pk, other.pk]))
        self.assertEqual(page.status_code, 403)


class CommentTests(TestCase):
    def setUp(self):
        self.teacher = make_teacher('comteach')
        self.classroom = Classroom.objects.create(name='C1', teacher=self.teacher)
        self.student = User.objects.create_user('comstud', password='pass12345')
        self.classroom.students.add(self.student)
        self.assignment = Assignment.objects.create(
            classroom=self.classroom, title='HW', description='Do it.')

    def test_member_can_comment_outsider_cannot(self):
        from .models import Comment
        self.client.login(username='comstud', password='pass12345')
        self.client.post(reverse('add_comment', args=[self.assignment.pk]), {'text': 'سوال دارم'})
        self.assertEqual(Comment.objects.count(), 1)

        User.objects.create_user('outsider2', password='pass12345')
        self.client.login(username='outsider2', password='pass12345')
        response = self.client.post(
            reverse('add_comment', args=[self.assignment.pk]), {'text': 'hack'})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Comment.objects.count(), 1)


class AIConfigTests(TestCase):
    """تنظیمات AI از ادمین: وقتی ردیف تنظیمات هست، مقدارهایش بر .env مقدم است."""

    def test_admin_config_overrides_env(self):
        from app.models import AIConfig
        from EnglishWoman.services import get_ai_settings, get_daily_limit
        AIConfig.objects.create(api_key='admin-key', model_name='gpt-4o', daily_limit=5)
        api_key, _, model, is_active = get_ai_settings()
        self.assertEqual(api_key, 'admin-key')
        self.assertEqual(model, 'gpt-4o')
        self.assertTrue(is_active)
        self.assertEqual(get_daily_limit(), 5)

    def test_blank_config_falls_back_to_env(self):
        from django.conf import settings
        from app.models import AIConfig
        from EnglishWoman.services import get_ai_settings
        AIConfig.objects.create()  # همه فیلدها خالی
        _, base_url, model, _ = get_ai_settings()
        self.assertEqual(base_url, settings.AI_BASE_URL)
        self.assertEqual(model, settings.AI_MODEL)

    def test_disabled_config_blocks_ai(self):
        from app.models import AIConfig
        from EnglishWoman.services import AIDisabled, chat_completion
        AIConfig.objects.create(api_key='k', is_active=False)
        with self.assertRaises(AIDisabled):
            chat_completion([{'role': 'user', 'content': 'hi'}])
