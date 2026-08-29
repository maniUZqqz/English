"""پرداخت با زرین‌پال (API v4) — پشتیبانی از سندباکس برای تست."""

from datetime import timedelta

import httpx
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .models import PLANS, Payment, Subscription


def _zp_base():
    if settings.ZARINPAL_SANDBOX:
        return 'https://sandbox.zarinpal.com'
    return 'https://payment.zarinpal.com'


def _zp_request(amount_toman, description, callback_url):
    """درخواست پرداخت — خروجی: authority یا None."""
    response = httpx.post(f'{_zp_base()}/pg/v4/payment/request.json', json={
        'merchant_id': settings.ZARINPAL_MERCHANT_ID,
        'amount': amount_toman,
        'currency': 'IRT',
        'description': description,
        'callback_url': callback_url,
    }, timeout=20)
    data = response.json().get('data') or {}
    if data.get('code') == 100:
        return data.get('authority')
    print('Zarinpal request failed:', response.text[:300])
    return None


def _zp_verify(amount_toman, authority):
    """تأیید پرداخت — خروجی: ref_id یا None."""
    response = httpx.post(f'{_zp_base()}/pg/v4/payment/verify.json', json={
        'merchant_id': settings.ZARINPAL_MERCHANT_ID,
        'amount': amount_toman,
        'currency': 'IRT',
        'authority': authority,
    }, timeout=20)
    data = response.json().get('data') or {}
    if data.get('code') in (100, 101):  # 101 = قبلاً تأیید شده
        return str(data.get('ref_id', ''))
    print('Zarinpal verify failed:', response.text[:300])
    return None


def _activate(user, plan_key):
    """فعال/تمدید اشتراک: از انقضای فعلی (اگر فعال است) ادامه می‌یابد."""
    plan = PLANS[plan_key]
    subscription, _ = Subscription.objects.get_or_create(
        user=user, defaults={'plan': plan_key, 'expires_at': timezone.now()})
    base = max(subscription.expires_at, timezone.now())
    subscription.plan = plan_key
    subscription.expires_at = base + timedelta(days=plan['days'])
    subscription.save()
    return subscription


@login_required(login_url='login')
def plans_page(request):
    subscription = Subscription.objects.filter(user=request.user).first()
    from EnglishWoman.services import get_daily_limit
    return render(request, 'billing/plans.html', {
        'plans': PLANS,
        'subscription': subscription if subscription and subscription.is_active else None,
        'current_limit': get_daily_limit(request.user),
        'gateway_ready': bool(settings.ZARINPAL_MERCHANT_ID),
        'payments': Payment.objects.filter(user=request.user, status='paid')[:5],
    })


@login_required(login_url='login')
def start_payment(request, plan_key):
    if request.method != 'POST' or plan_key not in PLANS:
        return redirect('plans')
    if not settings.ZARINPAL_MERCHANT_ID:
        messages.error(request, 'درگاه پرداخت هنوز پیکربندی نشده — ZARINPAL_MERCHANT_ID را در .env تنظیم کنید.')
        return redirect('plans')

    plan = PLANS[plan_key]
    payment = Payment.objects.create(user=request.user, plan=plan_key, amount=plan['price'])
    callback_url = settings.SITE_URL.rstrip('/') + reverse('payment_callback')
    try:
        authority = _zp_request(
            plan['price'],
            f"English Lady — اشتراک {plan['name']}",
            callback_url,
        )
    except Exception as e:
        print('Zarinpal connection error:', e)
        authority = None

    if not authority:
        payment.status = 'failed'
        payment.save()
        messages.error(request, 'اتصال به درگاه پرداخت ناموفق بود — دوباره تلاش کنید.')
        return redirect('plans')

    payment.authority = authority
    payment.save()
    return redirect(f'{_zp_base()}/pg/StartPay/{authority}')


@login_required(login_url='login')
def payment_callback(request):
    authority = request.GET.get('Authority', '')
    status = request.GET.get('Status', '')
    payment = Payment.objects.filter(
        authority=authority, user=request.user, status='pending').first()
    if not payment:
        messages.error(request, 'پرداخت پیدا نشد یا قبلاً پردازش شده.')
        return redirect('plans')

    if status != 'OK':
        payment.status = 'failed'
        payment.save()
        messages.error(request, 'پرداخت لغو شد.')
        return redirect('plans')

    try:
        ref_id = _zp_verify(payment.amount, authority)
    except Exception as e:
        print('Zarinpal verify connection error:', e)
        ref_id = None

    if not ref_id:
        payment.status = 'failed'
        payment.save()
        messages.error(request, 'تأیید پرداخت ناموفق بود — اگر مبلغ کم شده، تا ۷۲ ساعت برمی‌گردد.')
        return redirect('plans')

    payment.status = 'paid'
    payment.ref_id = ref_id
    payment.save()
    subscription = _activate(request.user, payment.plan)
    messages.success(
        request,
        f'پرداخت موفق! 🎉 اشتراک {PLANS[payment.plan]["name"]} تا '
        f'{subscription.expires_at:%Y-%m-%d} فعال شد. کد پیگیری: {ref_id}',
    )
    return redirect('plans')
