import logging

import dingtalk_stream
from django.conf import settings
from django.core.management.base import BaseCommand

from apps.channel.dingtalk.bot import YgaiBotHandler

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = '启动钉钉 Stream 机器人监听'

    def handle(self, *args, **options):
        app_key = settings.DINGTALK_APP_KEY
        app_secret = settings.DINGTALK_APP_SECRET

        if not app_key or not app_secret:
            self.stderr.write(self.style.ERROR(
                '请在 .env 中配置 DINGTALK_APP_KEY 和 DINGTALK_APP_SECRET'
            ))
            return

        credential = dingtalk_stream.Credential(app_key, app_secret)
        client = dingtalk_stream.DingTalkStreamClient(credential)
        client.register_callback_handler(
            dingtalk_stream.ChatbotMessage.TOPIC,
            YgaiBotHandler(),
        )

        from apps.todo.scheduler import start_scheduler
        start_scheduler()

        self.stdout.write(self.style.SUCCESS('钉钉 Stream Bot 启动中...'))
        client.start_forever()
