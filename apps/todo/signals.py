import threading
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Task
from .notion_client import sync_task_to_notion

@receiver(post_save, sender=Task)
def task_post_save(sender, instance, created, **kwargs):
    # Skip if we don't have an ID yet, though post_save usually guarantees it
    if not instance.id:
        return

    # Check if this is an update and the only change was notion_page_id
    # We don't want to loop infinitely when create_page updates the notion_page_id
    update_fields = kwargs.get('update_fields')
    if update_fields and 'notion_page_id' in update_fields and len(update_fields) == 1:
        return

    # 将网络请求放入后台线程，避免阻塞主线程响应
    threading.Thread(target=sync_task_to_notion, args=(instance.id,)).start()
