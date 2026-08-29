from django.contrib import admin
from .models import Payment, Subscription


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'expires_at', 'is_active')
    search_fields = ('user__username',)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'amount', 'status', 'ref_id', 'created_at')
    list_filter = ('status', 'plan')
    search_fields = ('user__username', 'authority', 'ref_id')
