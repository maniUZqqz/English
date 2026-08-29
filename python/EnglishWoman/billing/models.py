"""اشتراک و پرداخت — درگاه زرین‌پال."""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

# پلن‌ها: قیمت به تومان، مدت به روز، سقف درخواست AI در روز
PLANS = {
    'basic': {'name': 'پایه', 'price': 49000, 'days': 30, 'daily_limit': 50,
              'features': ['۵۰ درخواست AI در روز', 'همه ابزارهای هوشمند', 'پشتیبانی ایمیلی']},
    'pro': {'name': 'حرفه‌ای', 'price': 99000, 'days': 30, 'daily_limit': 300,
            'features': ['۳۰۰ درخواست AI در روز', 'همه ابزارهای هوشمند', 'معلم PDF نامحدود',
                         'پشتیبانی ۲۴/۷']},
}
# سقف پلن رایگان = مقدار AI_DAILY_LIMIT در ادمین/.env (پلن‌های پولی بالاتر از آن)


class Subscription(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subscription')
    plan = models.CharField(max_length=20)
    expires_at = models.DateTimeField()
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def is_active(self):
        return self.expires_at > timezone.now()

    @property
    def plan_info(self):
        return PLANS.get(self.plan)

    def __str__(self):
        state = 'active' if self.is_active else 'expired'
        return f"{self.user.username} — {self.plan} ({state} until {self.expires_at:%Y-%m-%d})"


class Payment(models.Model):
    STATUS_CHOICES = [('pending', 'در انتظار'), ('paid', 'پرداخت شد'), ('failed', 'ناموفق')]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    plan = models.CharField(max_length=20)
    amount = models.PositiveIntegerField()  # تومان
    authority = models.CharField(max_length=64, blank=True, db_index=True)
    ref_id = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} — {self.plan} — {self.amount} ({self.status})"
