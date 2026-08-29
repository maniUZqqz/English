"""کتابخانه شخصی: کتاب PDF آپلود کن، متنش استخراج و بخش‌بندی می‌شود، و AI مثل معلم درسش می‌دهد."""

from django.contrib.auth.models import User
from django.db import models


class Book(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='books')
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='books/%Y/%m/')
    num_pages = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}: {self.title}"


class BookSection(models.Model):
    """یک بخش از کتاب (~۱۵۰۰ کاراکتر) — واحد آموزش."""
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='sections')
    order = models.PositiveIntegerField()
    text = models.TextField()

    class Meta:
        unique_together = ('book', 'order')
        ordering = ['order']

    def __str__(self):
        return f"{self.book.title} — بخش {self.order}"


class SectionLesson(models.Model):
    """درس تولیدشده با AI برای یک بخش — کش می‌شود تا دوباره هزینه ندهد."""
    section = models.OneToOneField(BookSection, on_delete=models.CASCADE, related_name='lesson')
    lesson_html = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lesson for {self.section}"
