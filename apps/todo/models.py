from django.db import models


PRIORITY_CHOICES = [
    (1, '紧急'),
    (2, '重要'),
    (3, '普通'),
    (4, '低'),
]

STATUS_CHOICES = [
    ('pending', '待处理'),
    ('in_progress', '进行中'),
    ('done', '已完成'),
]

SOURCE_CHOICES = [
    ('dingtalk', '钉钉'),
    ('email', '邮件'),
    ('manual', '手动'),
]


class Task(models.Model):
    title = models.CharField('标题', max_length=200)
    description = models.TextField('描述', blank=True, default='')
    priority = models.IntegerField('优先级', choices=PRIORITY_CHOICES, default=2)
    status = models.CharField('状态', max_length=20, choices=STATUS_CHOICES, default='pending')
    source = models.CharField('来源', max_length=20, choices=SOURCE_CHOICES, default='manual')
    source_message_id = models.CharField('来源消息ID', max_length=200, blank=True, default='')
    due_date = models.DateTimeField('截止时间', null=True, blank=True)
    task_type = models.CharField('任务类型', max_length=50, blank=True, default='其他')
    notion_page_id = models.CharField('Notion ID', max_length=100, blank=True, default='')
    created_at = models.DateTimeField('创建时间', auto_now_add=True)
    updated_at = models.DateTimeField('更新时间', auto_now=True)

    class Meta:
        ordering = ['priority', '-created_at']
        verbose_name = '任务'
        verbose_name_plural = '任务'

    def __str__(self):
        return f'[{self.get_priority_display()}] {self.title}'
