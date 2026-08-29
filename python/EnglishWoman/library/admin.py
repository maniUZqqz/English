from django.contrib import admin
from .models import Book, BookSection, SectionLesson


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'num_pages', 'created_at')
    search_fields = ('title', 'user__username')


admin.site.register(BookSection)
admin.site.register(SectionLesson)
