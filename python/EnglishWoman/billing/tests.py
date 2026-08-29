"""تست‌های پرداخت و اشتراک — تماس با زرین‌پال ماک می‌شود."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import PLANS, Payment, Subscription


class PlanPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('payer', password='pass12345')
        self.client.login(username='payer', password='pass12345')

    def test_plans_page_renders(self):
        page = self.client.get(reverse('plans'))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'حرفه‌ای')

    def test_gateway_not_configured_blocks_payment(self):
        response = self.client.post(reverse('start_payment', args=['pro']), follow=True)
        self.assertContains(response, 'پیکربندی نشده')
        self.assertFalse(Payment.objects.exclude(status='pending').exists())


@override_settings(ZARINPAL_MERCHANT_ID='test-merchant-id')
class PaymentFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('payer', password='pass12345')
        self.client.login(username='payer', password='pass12345')

    @patch('billing.views._zp_request', return_value='AUTH123')
    def test_start_payment_redirects_to_gateway(self, _mock):
        response = self.client.post(reverse('start_payment', args=['pro']))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/pg/StartPay/AUTH123', response.url)
        payment = Payment.objects.get(user=self.user)
        self.assertEqual(payment.authority, 'AUTH123')
        self.assertEqual(payment.status, 'pending')

    @patch('billing.views._zp_verify', return_value='REF999')
    def test_successful_callback_activates_subscription(self, _mock):
        Payment.objects.create(
            user=self.user, plan='pro', amount=PLANS['pro']['price'], authority='AUTH123')
        response = self.client.get(
            reverse('payment_callback'), {'Authority': 'AUTH123', 'Status': 'OK'})
        self.assertRedirects(response, reverse('plans'))
        payment = Payment.objects.get(authority='AUTH123')
        self.assertEqual(payment.status, 'paid')
        self.assertEqual(payment.ref_id, 'REF999')
        subscription = Subscription.objects.get(user=self.user)
        self.assertTrue(subscription.is_active)
        self.assertEqual(subscription.plan, 'pro')

    def test_cancelled_callback_marks_failed(self):
        Payment.objects.create(
            user=self.user, plan='pro', amount=PLANS['pro']['price'], authority='AUTH123')
        self.client.get(reverse('payment_callback'), {'Authority': 'AUTH123', 'Status': 'NOK'})
        self.assertEqual(Payment.objects.get(authority='AUTH123').status, 'failed')
        self.assertFalse(Subscription.objects.exists())

    @patch('billing.views._zp_verify', return_value='REF1')
    def test_renewal_extends_from_current_expiry(self, _mock):
        future = timezone.now() + timedelta(days=10)
        Subscription.objects.create(user=self.user, plan='basic', expires_at=future)
        Payment.objects.create(
            user=self.user, plan='pro', amount=PLANS['pro']['price'], authority='A2')
        self.client.get(reverse('payment_callback'), {'Authority': 'A2', 'Status': 'OK'})
        subscription = Subscription.objects.get(user=self.user)
        # تمدید از انقضای فعلی، نه از امروز
        self.assertGreater(subscription.expires_at, future + timedelta(days=29))


class QuotaByPlanTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('quotauser', password='pass12345')

    def test_active_subscription_raises_daily_limit(self):
        from EnglishWoman.services import get_daily_limit
        base_limit = get_daily_limit(self.user)
        Subscription.objects.create(
            user=self.user, plan='pro',
            expires_at=timezone.now() + timedelta(days=10))
        self.assertEqual(get_daily_limit(self.user), PLANS['pro']['daily_limit'])
        self.assertNotEqual(get_daily_limit(self.user), base_limit)

    def test_expired_subscription_falls_back_to_free(self):
        from django.conf import settings
        from EnglishWoman.services import get_daily_limit
        Subscription.objects.create(
            user=self.user, plan='pro',
            expires_at=timezone.now() - timedelta(days=1))
        self.assertEqual(get_daily_limit(self.user), settings.AI_DAILY_LIMIT)
