import re
import logging
from apps.channel.models import ChannelUser, Message
from apps.todo.notion_client import save_link_to_knowledge_base
from apps.channel.wechat.url_parser import parse_url_metadata
from apps.ai.classifier import classify_article

logger = logging.getLogger('apps')

URL_REGEX = re.compile(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')

def handle_wechat_message(msg_type, content, from_user):
    # 1. 记录 ChannelUser 和 Message
    channel_user, _ = ChannelUser.objects.get_or_create(
        platform='wechat',
        platform_user_id=from_user,
        defaults={'name': from_user}
    )

    msg = Message.objects.create(
        channel_user=channel_user,
        platform='wechat',
        content=content,
        message_type=msg_type,
        direction='inbound'
    )

    # 2. 如果是文本消息，提取 URL 并存入 Notion
    if msg_type == 'text':
        urls = URL_REGEX.findall(content)
        if urls:
            logger.info(f"Found URLs in WeChat message from {from_user}: {urls}")
            for url in urls:
                try:
                    # 获取网页元数据
                    metadata = parse_url_metadata(url)
                    title = metadata.get('title') or f"WeChat Link from {from_user}"
                    source_name = metadata.get('source_name') or "未知来源"
                    date = metadata.get('date')

                    # AI 自动分类
                    category = classify_article(title)

                    save_link_to_knowledge_base(url, title, source_name, category, date)
                    logger.info(f"Successfully saved URL to Notion KB: {url}")
                except Exception as e:
                    logger.error(f"Failed to save URL to Notion KB: {url}, Error: {str(e)}")
            msg.processed = True
            msg.save()
            return f"成功提取并保存了 {len(urls)} 个链接到 Notion 知识库！"
        else:
            return "未发现任何链接，仅记录消息。"

    return "收到不支持的消息类型。"
