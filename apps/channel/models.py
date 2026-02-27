from django.db import models


PLATFORM_CHOICES = [
    ('dingtalk', '钉钉'),
    ('email', '邮件'),
    ('wechat', '企业微信'),
]

DIRECTION_CHOICES = [
    ('inbound', '收到'),
    ('outbound', '发出'),
]

MESSAGE_TYPE_CHOICES = [
    ('text', '文本'),
    ('image', '图片'),
    ('file', '文件'),
]

CLASSIFICATION_CHOICES = [
    ('urgent', '紧急'),
    ('important', '重要'),
    ('normal', '普通'),
    ('ignore', '可忽略'),
]


class ChannelUser(models.Model):
    platform = models.CharField('平台', max_length=20, choices=PLATFORM_CHOICES)
    platform_user_id = models.CharField('平台用户ID', max_length=100)
    name = models.CharField('用户名', max_length=100, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        unique_together = ['platform', 'platform_user_id']
        verbose_name = '渠道用户'
        verbose_name_plural = '渠道用户'

    def __str__(self):
        return f'{self.get_platform_display()} - {self.name or self.platform_user_id}'


class Message(models.Model):
    channel_user = models.ForeignKey(
        ChannelUser, on_delete=models.CASCADE, related_name='messages', verbose_name='用户',
    )
    platform = models.CharField('平台', max_length=20, choices=PLATFORM_CHOICES)
    content = models.TextField('内容')
    message_type = models.CharField('消息类型', max_length=20, choices=MESSAGE_TYPE_CHOICES, default='text')
    direction = models.CharField('方向', max_length=10, choices=DIRECTION_CHOICES, default='inbound')
    platform_message_id = models.CharField('平台消息ID', max_length=200, blank=True, default='')
    ai_classification = models.CharField(
        'AI分类', max_length=20, choices=CLASSIFICATION_CHOICES, blank=True, default='',
    )
    processed = models.BooleanField('已处理', default=False)
    created_at = models.DateTimeField('创建时间', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = '消息'
        verbose_name_plural = '消息'

    def __str__(self):
        return f'[{self.get_direction_display()}] {self.content[:50]}'
