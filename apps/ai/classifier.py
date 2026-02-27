import json
import logging
from http import HTTPStatus

import dashscope
from dashscope import Generation
from django.conf import settings

logger = logging.getLogger(__name__)

CLASSIFICATION_PROMPT = """你是一个消息分类助手。请将以下消息分类为以下四个类别之一：

- urgent: 紧急事项，需要立即处理（如紧急会议、线上事故、截止日期临近的任务）
- important: 重要事项，需要跟进但不紧急（如工作任务、项目安排、待办事项）
- normal: 普通消息，可以直接回复（如日常问候、简单问题、闲聊）
- ignore: 可忽略的消息（如广告、无意义的消息、系统通知）

只返回分类标签，不要返回其他内容。

消息内容：{content}"""

ARTICLE_CLASSIFICATION_PROMPT = """你是一个专业的文章分类助手。
请根据文章标题和描述（如果有的话），将文章分类到以下唯一匹配的分类中：
AI、产品、技术、生活、管理、其他

只输出一个分类名称，不要输出其他任何解释和符号。

文章标题：{title}
文章描述：{description}"""

ARTICLE_ANALYSIS_PROMPT = """你是一个专业的文章分析与评分专家。
请以中立、客观的视角仔细阅读以下文章内容（如果是纯文本的 HTML 请提取核心文本），并结合当前的行业背景和相关热点信息，完成以下三个任务：

1. **提取来源**：如果能从内容中看出文章来源（例如公众号名称、网站名称、作者等），请提取出来。如果无法确定，请返回"未知来源"。
2. **客观内容评分**：请摆脱强烈的情感色彩，客观评判文章的深度、原创性、逻辑结构和实际价值。给出一个1到5星的评分（必须是"⭐"、"⭐⭐"、"⭐⭐⭐"、"⭐⭐⭐⭐"、"⭐⭐⭐⭐⭐"之一）。如果是口水文、拼凑内容或者价值不高的营销文，请不要吝啬给出低分。
3. **结构化核心要点**：不要写成一段冗长的文字。请用 3 到 4 个精炼的 Bullet Points（用小圆点"•"开头）提炼出文章最核心的要点、新颖观点或实用结论。

请必须严格按照以下 JSON 格式输出，不要输出任何其他多余的字符或解释（确保能够被 JSON 解析）：

{{
  "source": "来源名称",
  "rating": "⭐⭐⭐",
  "summary": "• 核心要点一\n\n• 核心要点二\n\n• 核心要点三"
}}

---
以下是文章信息：
标题：{title}
URL: {url}
正文内容（截取部分）：
{content}
"""

def classify_message(content: str) -> str:
    if not settings.DASHSCOPE_API_KEY:
        logger.warning("DASHSCOPE_API_KEY 未配置，使用默认分类 normal")
        return 'normal'

    try:
        dashscope.api_key = settings.DASHSCOPE_API_KEY
        response = Generation.call(
            model='qwen-plus',
            messages=[{'role': 'user', 'content': CLASSIFICATION_PROMPT.format(content=content)}],
            result_format='message'
        )

        if response.status_code == HTTPStatus.OK:
            result = response.output.choices[0].message.content.strip().lower()
            if result in ('urgent', 'important', 'normal', 'ignore'):
                return result
            logger.warning("AI 返回了未知分类: %s，使用默认 normal", result)
            return 'normal'
        else:
            logger.error("消息分类失败: %s - %s", response.code, response.message)
            return 'normal'
    except Exception:
        logger.exception("消息分类异常")
        return 'normal'

def classify_article(title: str, description: str = "") -> str:
    if not settings.DASHSCOPE_API_KEY:
        logger.warning("DASHSCOPE_API_KEY 未配置，文章分类默认使用: 其他")
        return '其他'

    try:
        dashscope.api_key = settings.DASHSCOPE_API_KEY
        response = Generation.call(
            model='qwen-plus',
            messages=[{'role': 'user', 'content': ARTICLE_CLASSIFICATION_PROMPT.format(title=title, description=description)}],
            result_format='message'
        )

        if response.status_code == HTTPStatus.OK:
            result = response.output.choices[0].message.content.strip()
            # 兼容模型可能加上标点的情况
            result = result.strip('。，,.')
            if result in ('AI', '产品', '技术', '生活', '管理', '其他'):
                return result
            logger.warning(f"AI 预估了不在枚举中的分类: {result}，使用默认: 其他")
            return '其他'
        else:
            logger.error(f"文章分类失败: {response.code} - {response.message}")
            return '其他'
    except Exception as e:
        logger.exception(f"文章分类异常: {e}")
        return '其他'

def analyze_article_content(title: str, url: str, content: str) -> dict:
    """使用大模型对网页内容进行分析：提取来源、评分并生成概要。"""
    default_result = {
        "source": "未知来源",
        "rating": "⭐⭐⭐",
        "summary": "未能成功获取文章摘要。"
    }

    if not settings.DASHSCOPE_API_KEY:
        logger.warning("DASHSCOPE_API_KEY 未配置，跳过文章内容深度分析")
        return default_result

    # 截取正文前 5000 字符进行分析（控制 token 成本）
    content_preview = content[:5000] if content else ""

    try:
        dashscope.api_key = settings.DASHSCOPE_API_KEY
        response = Generation.call(
            model='qwen-plus',
            messages=[{'role': 'user', 'content': ARTICLE_ANALYSIS_PROMPT.format(title=title, url=url, content=content_preview)}],
            result_format='message'
        )

        if response.status_code == HTTPStatus.OK:
            result_text = response.output.choices[0].message.content.strip()
            # 去除可能包含的 markdown 代码块包裹 (```json ... ```)
            if result_text.startswith("```json"):
                result_text = result_text[7:]
            if result_text.startswith("```"):
                result_text = result_text[3:]
            if result_text.endswith("```"):
                result_text = result_text[:-3]

            result_text = result_text.strip()

            try:
                import json
                parsed_result = json.loads(result_text)
                return {
                    "source": parsed_result.get("source", "未知来源"),
                    "rating": parsed_result.get("rating", "⭐⭐⭐"),
                    "summary": parsed_result.get("summary", "暂无摘要")
                }
            except json.JSONDecodeError as e:
                logger.error(f"AI 解析文章返回的 JSON 格式错误: {result_text}, Error: {e}")
                return default_result
        else:
            logger.error(f"文章分析失败: {response.code} - {response.message}")
            return default_result
    except Exception as e:
        logger.exception(f"文章内容分析异常: {e}")
        return default_result
