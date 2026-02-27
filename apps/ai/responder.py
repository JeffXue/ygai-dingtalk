import logging
from http import HTTPStatus

import dashscope
from dashscope import Generation
from django.conf import settings

logger = logging.getLogger(__name__)

REPLY_PROMPT = """你是一个友好的个人助手。请简洁地回复以下消息。
回复要求：简短、有帮助、专业。不超过100字。

消息内容：{content}"""


def generate_reply(content: str) -> str:
    if not settings.DASHSCOPE_API_KEY:
        return '收到，我会尽快处理。'

    try:
        dashscope.api_key = settings.DASHSCOPE_API_KEY
        response = Generation.call(
            model='qwen-plus',
            messages=[{'role': 'user', 'content': REPLY_PROMPT.format(content=content)}],
            result_format='message'
        )

        if response.status_code == HTTPStatus.OK:
            return response.output.choices[0].message.content.strip()
        else:
            logger.error("生成回复失败: %s - %s", response.code, response.message)
            return '收到，我会尽快处理。'

    except Exception:
        logger.exception("生成回复异常")
        return '收到，我会尽快处理。'
