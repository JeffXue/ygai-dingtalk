import logging
from http import HTTPStatus

import dashscope
from dashscope import MultiModalConversation
from django.conf import settings

logger = logging.getLogger(__name__)

RECOGNIZE_PROMPT = "请详细描述这张图片的内容，并提取图片中所有可见的文字信息（OCR）。"


def recognize_images(image_urls: list[str]) -> list[str]:
    """逐张识别图片内容，返回每张图片的描述文本列表。"""
    if not settings.DASHSCOPE_API_KEY:
        logger.warning("DASHSCOPE_API_KEY 未配置，跳过图片识别")
        return []

    dashscope.api_key = settings.DASHSCOPE_API_KEY
    results = []

    for idx, url in enumerate(image_urls, 1):
        try:
            response = MultiModalConversation.call(
                model='qwen-vl-max',
                messages=[{
                    'role': 'user',
                    'content': [
                        {'image': url},
                        {'text': RECOGNIZE_PROMPT},
                    ],
                }],
            )

            if response.status_code == HTTPStatus.OK:
                text = response.output.choices[0].message.content[0].get('text', '').strip()
                description = f"图{idx}: {text}"
                logger.info("图片 %d 识别完成: %s", idx, description[:100])
            else:
                description = f"图{idx}: (识别失败: {response.code})"
                logger.error("图片 %d 识别失败: %s - %s", idx, response.code, response.message)

            results.append(description)

        except Exception:
            logger.exception("图片 %d 识别异常", idx)
            results.append(f"图{idx}: (识别异常)")

    return results
