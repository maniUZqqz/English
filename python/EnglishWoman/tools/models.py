from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# فاصله مرور جعبه‌های لایتنر (روز)
LEITNER_INTERVALS = {1: 1, 2: 2, 3: 4, 4: 7, 5: 15}


class SavedWord(models.Model):
    """دفتر لغات شخصی کاربر — با مرور فاصله‌دار لایتنر."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_words')
    word = models.CharField(max_length=100)
    translation = models.CharField(max_length=255, blank=True)
    synonyms = models.CharField(max_length=255, blank=True)
    antonyms = models.CharField(max_length=255, blank=True)
    example = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # لایتنر: جعبه ۱ (هر روز) تا جعبه ۵ (هر ۱۵ روز)
    box = models.PositiveSmallIntegerField(default=1)
    next_review = models.DateField(default=timezone.localdate)
    reviews = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('user', 'word')
        ordering = ['-created_at']

    def mark_reviewed(self, known):
        """به‌روزرسانی جعبه بعد از مرور: بلد بود → جعبه بالاتر، بلد نبود → جعبه ۱."""
        from datetime import timedelta
        self.box = min(self.box + 1, 5) if known else 1
        self.next_review = timezone.localdate() + timedelta(days=LEITNER_INTERVALS[self.box])
        self.reviews += 1
        self.save()

    @property
    def is_due(self):
        return self.next_review <= timezone.localdate()

    def __str__(self):
        return f"{self.user.username}: {self.word} (box {self.box})"


class WritingSubmission(models.Model):
    """تمرین نوشتاری — متن کاربر + تصحیح و نمره‌دهی AI (با معیار آیلتس)."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='writings')
    prompt = models.TextField()
    text = models.TextField()
    score = models.PositiveIntegerField(null=True, blank=True)   # 0 تا 100
    band = models.CharField(max_length=10, blank=True)           # باند آیلتس مثل 6.5
    feedback = models.TextField(blank=True)
    improved_version = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.score}/100 (band {self.band})"


class ChatMessage(models.Model):
    """حافظه‌ی گفتگوی چت‌بات — بین جلسات کاربر حفظ می‌شود."""
    ROLE_CHOICES = [('user', 'user'), ('assistant', 'assistant')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.user.username} ({self.role}): {self.content[:40]}"
