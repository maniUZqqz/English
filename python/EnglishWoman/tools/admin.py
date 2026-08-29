from django.contrib import admin
from .models import ChatMessage, SavedWord


@admin.register(SavedWord)
class SavedWordAdmin(admin.ModelAdmin):
    list_display = ('word', 'user', 'translation', 'box', 'next_review', 'created_at')
    list_filter = ('box',)
    search_fields = ('word', 'translation', 'user__username')


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'content', 'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'content')
