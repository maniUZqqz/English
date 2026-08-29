# app/apps.py
from django.apps import AppConfig as DjangoAppConfig

class MainConfig(DjangoAppConfig):
    name = 'app'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        import app.signals        # لود سیگنال‌ها
