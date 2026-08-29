"""
سهمیه مصرف AI و استریک فعالیت روزانه.

- consume_ai_quota(user): قبل از هر فراخوانی مدل صدا زده می‌شود؛ اگر سقف روزانه
  پر شده باشد QuotaExceeded می‌اندازد. خودِ فراخوانی، فعالیت امروز را هم ثبت می‌کند.
- record_activity(user): برای فعالیت‌های غیر-AI (پاسخ آزمون، ذخیره لغت و…).
- current_streak(user): تعداد روزهای پیاپی فعالیت تا امروز.
"""

from datetime import timedelta

from django.db.models import F
from django.utils import timezone

QUOTA_MESSAGE = 'سهمیه‌ی روزانه‌ی هوش مصنوعی شما تمام شده است. فردا دوباره تلاش کنید.'


class QuotaExceeded(Exception):
    """سقف مصرف روزانه AI پر شده است."""

    def __init__(self, message=QUOTA_MESSAGE):
        super().__init__(message)


def record_activity(user):
    """ثبت اینکه کاربر امروز فعال بوده (برای استریک)."""
    from .models import DailyActivity
    activity, _ = DailyActivity.objects.get_or_create(user=user, date=timezone.localdate())
    return activity


def consume_ai_quota(user, amount=1):
    """
    یک واحد از سهمیه امروز کاربر کم می‌کند (اتمیک، امن در برابر همزمانی).
    اگر سهمیه کافی نباشد QuotaExceeded می‌اندازد.
    """
    from .models import DailyActivity
    from EnglishWoman.services import get_daily_limit
    limit = get_daily_limit()
    activity = record_activity(user)
    updated = DailyActivity.objects.filter(
        pk=activity.pk,
        ai_requests__lte=limit - amount,
    ).update(ai_requests=F('ai_requests') + amount)
    if not updated:
        raise QuotaExceeded()


def usage_today(user):
    """(مصرف امروز، سقف) — برای نمایش در داشبورد."""
    from .models import DailyActivity
    from EnglishWoman.services import get_daily_limit
    limit = get_daily_limit()
    activity = DailyActivity.objects.filter(user=user, date=timezone.localdate()).first()
    return (activity.ai_requests if activity else 0), limit


def current_streak(user):
    """تعداد روزهای پیاپی فعالیت. اگر امروز هنوز فعالیتی نبوده، زنجیره تا دیروز حساب می‌شود."""
    from .models import DailyActivity
    today = timezone.localdate()
    dates = set(
        DailyActivity.objects.filter(user=user, date__gte=today - timedelta(days=366))
        .values_list('date', flat=True)
    )
    day = today if today in dates else today - timedelta(days=1)
    streak = 0
    while day in dates:
        streak += 1
        day -= timedelta(days=1)
    return streak
