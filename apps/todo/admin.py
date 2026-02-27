from django.contrib import admin
from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ['title', 'priority', 'status', 'source', 'due_date', 'created_at']
    list_filter = ['priority', 'status', 'source']
    search_fields = ['title', 'description']
    list_editable = ['priority', 'status']
