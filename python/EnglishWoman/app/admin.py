from django.contrib import admin
from .models import AIConfig, DailyActivity, Question, UserResponse, UserLevel, UserProfile


@admin.register(AIConfig)
class AIConfigAdmin(admin.ModelAdmin):
    """تنظیمات هوش مصنوعی — کلید API را اینجا وارد کنید."""
    list_display = ('__str__', 'is_active', 'daily_limit', 'updated_at')
    fieldsets = (
        ('اتصال به سرویس AI', {
            'fields': ('api_key', 'base_url', 'model_name'),
            'description': 'هر فیلدی که خالی بماند، از فایل .env خوانده می‌شود.',
        }),
        ('کنترل مصرف', {
            'fields': ('daily_limit', 'is_active'),
        }),
    )

    def has_add_permission(self, request):
        # فقط یک ردیف تنظیمات مجاز است
        return not AIConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'progress')
    list_filter = ('role',)
    list_editable = ('role',)
    search_fields = ('user__username', 'user__email')


@admin.register(UserLevel)
class UserLevelAdmin(admin.ModelAdmin):
    list_display = ('user', 'level_title', 'created_at')
    search_fields = ('user__username',)


@admin.register(DailyActivity)
class DailyActivityAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'ai_requests')
    list_filter = ('date',)
    search_fields = ('user__username',)


admin.site.register(Question)
admin.site.register(UserResponse)
