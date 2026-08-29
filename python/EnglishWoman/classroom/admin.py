from django.contrib import admin
from .models import (Announcement, Assignment, Attendance, ClassExam,
                     ClassSchedule, ClassSession, Classroom, Comment,
                     ExamAttempt, ExamQuestion, Submission)


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    list_display = ('name', 'level', 'teacher', 'join_code', 'is_active', 'created_at')
    list_filter = ('level', 'is_active')
    search_fields = ('name', 'teacher__username', 'join_code')
    filter_horizontal = ('students',)


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'classroom', 'due_date', 'created_at')
    list_filter = ('classroom',)
    search_fields = ('title',)


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'grade', 'submitted_at')
    list_filter = ('assignment__classroom',)
    search_fields = ('student__username', 'assignment__title')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'classroom', 'created_at')
    list_filter = ('classroom',)


@admin.register(ClassSession)
class ClassSessionAdmin(admin.ModelAdmin):
    list_display = ('classroom', 'date', 'topic')
    list_filter = ('classroom',)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'session', 'status')
    list_filter = ('status', 'session__classroom')


@admin.register(ClassExam)
class ClassExamAdmin(admin.ModelAdmin):
    list_display = ('title', 'classroom', 'is_published', 'duration_minutes', 'created_at')
    list_filter = ('classroom', 'is_published')


class ExamQuestionInline(admin.TabularInline):
    model = ExamQuestion
    extra = 0


@admin.register(ExamAttempt)
class ExamAttemptAdmin(admin.ModelAdmin):
    list_display = ('student', 'exam', 'score', 'finished_at')
    list_filter = ('exam__classroom',)


admin.site.register(ClassSchedule)
admin.site.register(ExamQuestion)
admin.site.register(Comment)
