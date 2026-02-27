from django.contrib import admin
from .models import ChannelUser, Message


@admin.register(ChannelUser)
class ChannelUserAdmin(admin.ModelAdmin):
    list_display = ['name', 'platform', 'platform_user_id', 'created_at']
    list_filter = ['platform']
    search_fields = ['name', 'platform_user_id']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['channel_user', 'platform', 'direction', 'message_type', 'ai_classification', 'processed', 'created_at']
    list_filter = ['platform', 'direction', 'ai_classification', 'processed']
    search_fields = ['content']
    readonly_fields = ['created_at']
