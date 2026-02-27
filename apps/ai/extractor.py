import json
import logging
from datetime import datetime
from http import HTTPStatus

import dashscope
from dashscope import Generation
from django.conf import settings

from django.utils import timezone

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = (
    "\u4f60\u662f\u4e00\u4e2a\u4efb\u52a1\u63d0\u53d6\u52a9\u624b\u3002\u5f53\u524d\u7cfb\u7edf\u65f6\u95f4\u662f\uff1a{current_time}\u3002\n"
    "\u8bf7\u4ece\u4ee5\u4e0b\u6d88\u606f\u4e2d\u63d0\u53d6\u4efb\u52a1\u4fe1\u606f\u3002\u5982\u679c\u6d88\u606f\u4e2d\u5305\u542b\"\u660e\u5929\"\u3001\"\u4e0b\u5468\"\u3001\"\u4e00\u5c0f\u65f6\u540e\"\u7b49\u76f8\u5bf9\u65f6\u95f4\uff0c\u8bf7\u52a1\u5fc5\u57fa\u4e8e\u5f53\u524d\u7cfb\u7edf\u65f6\u95f4\u8fdb\u884c\u63a8\u7b97\u3002\n"
    "\n"
    "**\u91cd\u8981\uff1a\u5982\u679c\u6d88\u606f\u4e2d\u5305\u542b\u591a\u4e2a\u4e0d\u540c\u7684\u4efb\u52a1\uff08\u4f8b\u5982\u6765\u81ea\u591a\u5f20\u56fe\u7247\u3001\u591a\u6761\u804a\u5929\u8bb0\u5f55\uff09\uff0c\u8bf7\u5c06\u6bcf\u4e2a\u4efb\u52a1\u4f5c\u4e3a\u72ec\u7acb\u7684\u5bf9\u8c61\u8fd4\u56de\u3002**\n"
    "\n"
    "\u8bf7\u4ee5 JSON \u6570\u7ec4\u683c\u5f0f\u8fd4\u56de\uff0c\u6bcf\u4e2a\u4efb\u52a1\u662f\u6570\u7ec4\u4e2d\u7684\u4e00\u4e2a\u5bf9\u8c61\uff1a\n"
    "[\n"
    "  {{\n"
    '    "title": "\u4efb\u52a1\u6807\u9898\uff08\u7b80\u6d01\u660e\u4e86\uff0c\u4e0d\u8d85\u8fc750\u5b57\uff09",\n'
    '    "description": "\u4efb\u52a1\u63cf\u8ff0\uff08\u53ef\u9009\uff0c\u8865\u5145\u8bf4\u660e\uff09",\n'
    '    "priority": 2, // 1\u8868\u793a\u9ad8\uff0c2\u8868\u793a\u4e2d\uff0c3\u8868\u793a\u4f4e\uff0c\u9ed8\u8ba42\n'
    '    "task_type": "\u4efb\u52a1\u7c7b\u578b\uff0c\u5fc5\u987b\u4ece\u4ee5\u4e0b\u9009\u9879\u4e2d\u9009\u62e9\u4e00\u4e2a\uff1a\u751f\u4ea7\u95ee\u9898\u3001AI\u4ea7\u54c1\u3001\u7ba1\u7406\u3001\u8fed\u4ee3\u4e8b\u9879\u3001\u6280\u672f\u8c03\u7814\u3001\u8fd0\u7ef4\u4e8b\u9879\u3001\u4fe1\u606f\u5316\u3001\u5ba2\u6237\u652f\u6301\u3001\u5176\u4ed6\u3002\u8bf7\u6839\u636e\u4efb\u52a1\u5185\u5bb9\u667a\u80fd\u5224\u65ad\uff0c\u4f8b\u5982\uff1a\u591a\u7ef4\u8868/\u591a\u7ef4\u8868\u683c/\u8fd0\u8425\u7cfb\u7edf\u76f8\u5173\u7684\u4e8b\u9879\u5c5e\u4e8e\'\u4fe1\u606f\u5316\'\uff0c\u670d\u52a1\u5668/\u673a\u623f/\u7f51\u7edc\u95ee\u9898\u5c5e\u4e8e\'\u8fd0\u7ef4\u4e8b\u9879\'\uff0cbug\u4fee\u590d\u5c5e\u4e8e\'\u751f\u4ea7\u95ee\u9898\'\uff0c\u65e5\u5e38\u5f00\u53d1\u5c5e\u4e8e\'\u8fed\u4ee3\u4e8b\u9879\'\uff0c\u6280\u672f\u9884\u7814\u5c5e\u4e8e\'\u6280\u672f\u8c03\u7814\'\u3002\u5982\u679c\u786e\u5b9e\u65e0\u6cd5\u5f52\u7c7b\uff0c\u8bf7\u9009\u62e9\'\u5176\u4ed6\'",\n'
    '    "due_date": "\u622a\u6b62\u65f6\u95f4\uff08ISO 8601 \u683c\u5f0f\uff0c\u5982 2026-02-25T18:00:00\uff0c\u5982\u679c\u6ca1\u6709\u5219\u4e3a null\uff09"\n'
    "  }}\n"
    "]\n"
    "\n"
    "\u5373\u4f7f\u53ea\u6709\u4e00\u4e2a\u4efb\u52a1\uff0c\u4e5f\u8bf7\u8fd4\u56de\u6570\u7ec4\u683c\u5f0f\u3002\u53ea\u8fd4\u56de JSON \u6570\u7ec4\uff0c\u4e0d\u8981\u8fd4\u56de\u5176\u4ed6\u5185\u5bb9\u3002\n"
    "\n"
    "\u6d88\u606f\u5185\u5bb9\uff1a{content}"
)


def extract_task(content: str, image_urls: list = None, sender_name: str = None) -> dict:
    default = {'title': content[:100], 'description': '', 'priority': 2, 'task_type': '\u5176\u4ed6', 'due_date': None}

    if not settings.DASHSCOPE_API_KEY:
        logger.warning("DASHSCOPE_API_KEY \u672a\u914d\u7f6e\uff0c\u4f7f\u7528\u6d88\u606f\u5185\u5bb9\u4f5c\u4e3a\u4efb\u52a1\u6807\u9898")
        return default

    try:
        current_time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        prompt_context = ""
        if sender_name:
            prompt_context = f"\n\u5f53\u524d\u8bf7\u6c42\u63d0\u53d6\u4efb\u52a1\u7684\u7528\u6237\u662f\uff1a\u3010{sender_name}\u3011\u3002\n" + \
                             "\u8bf7\u6ce8\u610f\uff1a\n" + \
                             "1. \u5982\u679c\u6d88\u606f\u4e2d\u5305\u542b\u591a\u4e2a\u4efb\u52a1\uff0c\u8bf7\u53ea\u63d0\u53d6\u5206\u914d\u7ed9\u8be5\u7528\u6237\uff08\u6216\u8005\u6d89\u53ca\u5168\u516c\u53f8/\u5168\u90e8\u95e8\uff09\u7684\u4efb\u52a1\uff0c\u76f4\u63a5\u5ffd\u7565\u660e\u786e\u5206\u914d\u7ed9\u5176\u4ed6\u4eba\u7684\u5177\u4f53\u4efb\u52a1\u3002\n" + \
                             "2. \u4e0d\u8981\u628a\u4efb\u52a1\u62c6\u5f97\u592a\u7ec6\uff0c\u5c3d\u91cf\u4fdd\u6301\u4efb\u52a1\u7684\u5b8c\u6574\u6027\u548c\u8fde\u8d2f\u6027\u3002"

        prompt = EXTRACT_PROMPT.format(current_time=current_time_str, content=content) + prompt_context

        dashscope.api_key = settings.DASHSCOPE_API_KEY

        # \u7ec4\u88c5 messages \u8f7d\u8377
        if image_urls:
            model = 'qwen-vl-max'
            # qwen-vl \u6a21\u578b\u8981\u6c42 content \u662f\u4e00\u4e2a\u6570\u7ec4\u683c\u5f0f
            content_list = []
            for url in image_urls:
                content_list.append({'image': url})
            content_list.append({'text': prompt})

            messages = [
                {
                    'role': 'user',
                    'content': content_list
                }
            ]
            logger.info(f"\u4f7f\u7528\u591a\u6a21\u6001\u5927\u6a21\u578b {model} \u8fdb\u884c\u89e3\u6790\uff0c\u5305\u542b {len(image_urls)} \u5f20\u56fe\u7247")
        else:
            model = 'qwen-max'
            messages = [{'role': 'user', 'content': prompt}]

        response = dashscope.MultiModalConversation.call(model=model, messages=messages) if image_urls else Generation.call(model=model, messages=messages, result_format='message')

        if response.status_code == HTTPStatus.OK:
            if image_urls:
                text = response.output.choices[0].message.content[0].get('text', '').strip()
            else:
                text = response.output.choices[0].message.content.strip()

            # \u6e05\u7406 Qwen \u53ef\u80fd\u8fd4\u56de\u7684 Markdown \u4ee3\u7801\u5757
            if text.startswith('```json'):
                text = text[7:]
            if text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()

            data = json.loads(text)
            logger.info(f"\u4efb\u52a1\u63d0\u53d6\u7ed3\u679c: {data}")

            # \u7edf\u4e00\u5904\u7406\u6210\u5217\u8868\uff08\u517c\u5bb9\u6a21\u578b\u5076\u5c14\u8fd4\u56de\u5355\u4e2a\u5bf9\u8c61\u7684\u60c5\u51b5\uff09
            items = data if isinstance(data, list) else [data]

            results = []
            for item in items:
                result = {
                    'title': item.get('title') or content[:100],
                    'description': item.get('description') or '',
                    'priority': item.get('priority') or 2,
                    'task_type': item.get('task_type') or '\u5176\u4ed6',
                    'due_date': None,
                }

                if item.get('due_date'):
                    try:
                        dt = datetime.fromisoformat(item['due_date'])
                        if timezone.is_naive(dt):
                            dt = timezone.make_aware(dt)
                        result['due_date'] = dt
                    except (ValueError, TypeError):
                        pass
                results.append(result)

            return results
        else:
            logger.error("\u4efb\u52a1\u63d0\u53d6\u5931\u8d25: %s - %s", response.code, response.message)
            return default

    except Exception:
        logger.exception("\u4efb\u52a1\u63d0\u53d6\u5f02\u5e38")
        return default
