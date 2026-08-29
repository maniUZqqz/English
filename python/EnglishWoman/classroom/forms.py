from django import forms
from .models import (Announcement, Assignment, ClassExam, ClassSchedule,
                     ClassSession, Classroom, Comment, ExamQuestion, Submission)

MAX_UPLOAD_MB = 10


class ClassroomForm(forms.ModelForm):
    class Meta:
        model = Classroom
        fields = ['name', 'level', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'مثلاً: انگلیسی B1 — کلاس عصر'}),
            'level': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                                 'placeholder': 'برنامه، اهداف، کتاب‌ها…'}),
        }


class JoinClassForm(forms.Form):
    join_code = forms.CharField(
        max_length=8,
        widget=forms.TextInput(attrs={'class': 'form-control text-uppercase en',
                                      'placeholder': 'کد کلاس، مثلاً X7K2PM'}),
    )

    def clean_join_code(self):
        return self.cleaned_data['join_code'].strip().upper()


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'body']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'عنوان'}),
            'body': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'متن اطلاعیه…'}),
        }


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'due_date']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'عنوان تکلیف'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                                 'placeholder': 'زبان‌آموزها چه کاری باید انجام دهند؟'}),
            'due_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['text', 'file']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control en', 'rows': 8,
                                          'placeholder': 'Write your answer in English…'}),
            'file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file and file.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f'حجم فایل نباید بیشتر از {MAX_UPLOAD_MB} مگابایت باشد.')
        return file


class GradeForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['grade', 'feedback']
        widgets = {
            'grade': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 100,
                                              'placeholder': 'نمره'}),
            'feedback': forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                              'placeholder': 'بازخورد برای زبان‌آموز…'}),
        }

    def clean_grade(self):
        grade = self.cleaned_data.get('grade')
        if grade is not None and grade > 100:
            raise forms.ValidationError('نمره باید بین ۰ تا ۱۰۰ باشد.')
        return grade


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                          'placeholder': 'سوال یا نظر خود را بنویسید…'}),
        }


class SessionForm(forms.ModelForm):
    class Meta:
        model = ClassSession
        fields = ['date', 'topic']
        widgets = {
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'topic': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'موضوع جلسه (اختیاری)'}),
        }


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = ClassSchedule
        fields = ['weekday', 'start_time', 'end_time']
        widgets = {
            'weekday': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
        }


class ExamForm(forms.ModelForm):
    class Meta:
        model = ClassExam
        fields = ['title', 'description', 'duration_minutes']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'عنوان آزمون'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2,
                                                 'placeholder': 'توضیحات (اختیاری)'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 180}),
        }


class ExamQuestionForm(forms.ModelForm):
    class Meta:
        model = ExamQuestion
        fields = ['text', 'option_a', 'option_b', 'option_c', 'option_d', 'correct_option']
        widgets = {
            'text': forms.Textarea(attrs={'class': 'form-control en', 'rows': 2, 'placeholder': 'Question text'}),
            'option_a': forms.TextInput(attrs={'class': 'form-control en', 'placeholder': 'Option A'}),
            'option_b': forms.TextInput(attrs={'class': 'form-control en', 'placeholder': 'Option B'}),
            'option_c': forms.TextInput(attrs={'class': 'form-control en', 'placeholder': 'Option C'}),
            'option_d': forms.TextInput(attrs={'class': 'form-control en', 'placeholder': 'Option D'}),
            'correct_option': forms.Select(attrs={'class': 'form-select'}),
        }
