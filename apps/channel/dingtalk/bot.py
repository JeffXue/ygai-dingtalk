import json
import logging
import re

import httpx
from bs4 import BeautifulSoup
from dingtalk_stream import AckMessage, ChatbotHandler

from apps.channel.models import ChannelUser, Message
from apps.ai.classifier import classify_message, classify_article
from apps.ai.extractor import extract_task
from apps.ai.responder import generate_reply
from apps.todo.models import Task
from apps.todo.notion_client import save_link_to_knowledge_base

logger = logging.getLogger(__name__)


class YgaiBotHandler(ChatbotHandler):
    """处理钉钉机器人收到的消息"""

    async def process(self, callback):
        try:
            from asgiref.sync import sync_to_async

            incoming = callback.data
            logger.info("收到原始消息: %s", incoming)

            # 处理富文本/图文/聊天记录转发消息
            msgtype = incoming.get('msgtype', '')
            text = ''
            download_codes = []

            if msgtype == 'richText':
                rich_text = incoming.get('content', {}).get('richText', [])
                for item in rich_text:
                    if 'text' in item:
                        text += item['text']
                    elif 'downloadCode' in item:
                        download_codes.append(item['downloadCode'])
            elif msgtype == 'chatRecord':
                # 解析转发的聊天记录
                try:
                    chat_records = json.loads(incoming.get('content', {}).get('chatRecord', '[]'))
                    record_texts = []
                    for record in chat_records:
                        record_msg_type = record.get('msgType', '')
                        if record_msg_type == 'text':
                            record_texts.append(record.get('content', ''))
                        elif record_msg_type == 'richText':
                            for item in record.get('richText', []):
                                if item.get('msgType') == 'text':
                                    record_texts.append(item.get('content', ''))
                                elif item.get('msgType') == 'picture' and 'downloadCode' in item:
                                    download_codes.append(item['downloadCode'])

                    text = "\n".join(record_texts)
                except json.JSONDecodeError:
                    text = incoming.get('content', {}).get('summary', '')
            elif msgtype == 'picture':
                # 单纯的一张图片
                code = incoming.get('content', {}).get('downloadCode', '')
                if code:
                    download_codes.append(code)
                text = "这是图片消息，请提取图片中的任务信息" # 给 AI 补充一个默认文本提示

                # 如果是纯图片消息，我们在数据库里把 message_type 设为 image
                msg_record_type = 'image'
            else:
                text = incoming.get('text', {}).get('content', '')
                msg_record_type = 'text'

            # 只有在还没被设为 image 的情况下，如果是文本/图文，设为 text
            if 'msg_record_type' not in locals():
                msg_record_type = 'text'

            text = text.strip()
            sender_id = incoming.get('senderStaffId', '')
            sender_nick = incoming.get('senderNick', '')
            msg_id = incoming.get('msgId', '')
            conversation_id = incoming.get('conversationId', '')

            if not text and not download_codes:
                self.reply_text('请发送文本或图片消息', callback)
                return AckMessage.STATUS_OK, 'OK'

            logger.info("收到消息 from %s: %s (附带 %d 张图片)", sender_nick, text, len(download_codes))

            # 1. 如果是群聊中@机器人，钉钉会将@机器人的文本也带过来（如 "@YGAI 帮我写个请假条"）
            clean_text = text
            if incoming.get('conversationType') == '2':  # 如果是群聊
                at_users = incoming.get('atUsers', [])
                for at_user in at_users:
                    at_dingtalk_id = at_user.get('dingtalkId')
                    clean_text = clean_text.replace(f'@{at_dingtalk_id}', '').strip()

            # URL 提取与信息获取
            urls = re.findall(r'https?://[^\s\u4e00-\u9fff<>"\'\n\r]+', clean_text)
            url_infos = []
            if urls:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}) as client:
                    for url in urls:
                        # 检查链接是否已经存在
                        from apps.todo.notion_client import check_link_exists_in_knowledge_base
                        existing_info = await sync_to_async(check_link_exists_in_knowledge_base)(url)
                        if existing_info and existing_info.get("exists"):
                            logger.info("URL 已存在于知识库，跳过抓取与保存: %s", url)
                            url_infos.append({
                                "url": url,
                                "title": existing_info["title"],
                                "category": existing_info["category"],
                                "rating": existing_info["rating"],
                                "summary": existing_info["summary"],
                                "is_existing": True
                            })
                            continue

                        title = url
                        publish_date = None
                        try:
                            response = await client.get(url)
                            if response.status_code == 200:
                                soup = BeautifulSoup(response.text, 'html.parser')

                                # 1. 尝试获取标题
                                # 微信文章的真实标题一般在 meta 标签中，优先取 og:title
                                og_title = soup.find('meta', property='og:title')
                                if og_title and og_title.get('content'):
                                    title = og_title['content'].strip()
                                elif soup.title and soup.title.string:
                                    title = soup.title.string.strip()

                                # 2. 尝试获取文章发布时间
                                # 从 Open Graph 获取
                                og_time = soup.find('meta', property='article:published_time') or soup.find('meta', property='og:article:published_time')
                                if og_time and og_time.get('content'):
                                    publish_date = og_time['content'].strip()
                                else:
                                    # 从常见的 meta name 获取
                                    meta_time = soup.find('meta', attrs={'name': 'publishdate'}) or soup.find('meta', attrs={'name': 'pubdate'})
                                    if meta_time and meta_time.get('content'):
                                        publish_date = meta_time['content'].strip()
                                    else:
                                        # 特殊处理微信文章的发布时间 (微信页面中通常有一个特定属性或注释，这里尝试获取 js 变量)
                                        time_match = re.search(r'create_time\s*=\s*"([^"]+)"', response.text) or re.search(r'ct\s*=\s*"(\d{10})"', response.text)
                                        if time_match:
                                            time_val = time_match.group(1)
                                            if time_val.isdigit() and len(time_val) == 10:
                                                from datetime import datetime, timezone, timedelta
                                                # 微信的 Unix 时间戳已经是 UTC 时间，将其转换为北京时间 (UTC+8) 的带时区格式
                                                # 先获取 UTC 的 datetime 对象
                                                dt_utc = datetime.fromtimestamp(int(time_val), tz=timezone.utc)
                                                # 再转换为北京时间的 datetime 对象
                                                dt_beijing = dt_utc.astimezone(timezone(timedelta(hours=8)))
                                                publish_date = dt_beijing.isoformat()
                                            else:
                                                publish_date = time_val
                                        else:
                                            # 如果找不到任何时间，对于非微信的文章也尝试用正则抓取类似 "2024-02-27" 这样的日期
                                            date_match = re.search(r'\b(20[12]\d[-/年](0?[1-9]|1[012])[-/月](0?[1-9]|[12][0-9]|3[01])[日]?)\b', response.text)
                                            if date_match:
                                                import datetime as dt_lib
                                                raw_date = date_match.group(1).replace('年', '-').replace('月', '-').replace('日', '').replace('/', '-')
                                                try:
                                                    # 尝试转换为标准的带时区 ISO 格式
                                                    parsed_date = dt_lib.datetime.strptime(raw_date, "%Y-%m-%d")
                                                    publish_date = parsed_date.replace(tzinfo=dt_lib.timezone(dt_lib.timedelta(hours=8))).isoformat()
                                                except ValueError:
                                                    publish_date = raw_date

                        except Exception as e:
                            logger.warning("获取 URL 标题或时间失败 %s: %s", url, e)

                        category = await sync_to_async(classify_article)(title)

                        # 使用 AI 进行深度分析：提取真实来源、评分、概要
                        from apps.ai.classifier import analyze_article_content
                        content_text = soup.get_text(separator='\n', strip=True) if 'soup' in locals() else ""
                        analysis_result = await sync_to_async(analyze_article_content)(title, url, content_text)

                        source = analysis_result.get("source", sender_nick)
                        if source == "未知来源":
                            source = sender_nick

                        rating = analysis_result.get("rating", "⭐⭐⭐")
                        summary = analysis_result.get("summary", "暂无摘要")

                        logger.info("AI 网页分析结果 - URL: %s | 标题: %s | 分类: %s | 发布时间: %s | 来源: %s | 评分: %s",
                                    url, title, category, publish_date, source, rating)

                        try:
                            await sync_to_async(save_link_to_knowledge_base)(url, title, source, category, publish_date, rating, summary)
                            url_infos.append({
                                "url": url,
                                "title": title,
                                "category": category,
                                "rating": rating,
                                "summary": summary
                            })
                        except Exception as e:
                            logger.error("保存 URL 到 Notion 失败 %s: %s", url, e)

            # 2. 识别/创建渠道用户
            channel_user, _ = await sync_to_async(ChannelUser.objects.get_or_create)(
                platform='dingtalk',
                platform_user_id=sender_id,
                defaults={'name': sender_nick},
            )

            # 3. 准备图片 URLs (多张图片)
            image_urls = []
            if download_codes:
                from .utils import get_download_url
                for code in download_codes:
                    url = await get_download_url(code, incoming.get('robotCode', ''))
                    if url:
                        image_urls.append(url)

            # 4. 保存原始消息
            # 如果是多张图片，我们将 URLs 用逗号连接存入数据库
            saved_content = text
            if msgtype == 'picture':
                saved_content = ",".join(image_urls) if image_urls else text

            message = await sync_to_async(Message.objects.create)(
                channel_user=channel_user,
                platform='dingtalk',
                content=saved_content,
                message_type=msg_record_type,
                direction='inbound',
                platform_message_id=msg_id,
            )

            # 5. 逐张识别图片内容
            image_descriptions = []
            if image_urls:
                from apps.ai.recognizer import recognize_images
                image_descriptions = await sync_to_async(recognize_images)(image_urls)
                logger.info("图片识别结果: %s", image_descriptions)

            # 6. AI 分类 (将图片识别文本拼入，让分类更准确)
            if image_descriptions:
                full_text = clean_text + "\n\n" + "\n".join(image_descriptions) if clean_text else "\n".join(image_descriptions)
            else:
                full_text = clean_text

            if not full_text:
                classification = 'important'
            else:
                classification = await sync_to_async(classify_message)(full_text)

            message.ai_classification = classification
            message.processed = True
            await sync_to_async(message.save)(update_fields=['ai_classification', 'processed'])
            logger.info("AI 分类结果: %s", classification)

            is_group = incoming.get('conversationType') == '2'

            # 7. 根据分类处理
            if classification in ('urgent', 'important'):
                if image_urls:
                    task_info_list = await sync_to_async(extract_task)(full_text, image_urls=image_urls, sender_name=sender_nick)
                else:
                    task_info_list = await sync_to_async(extract_task)(full_text, sender_name=sender_nick)

                # 如果提取出的是单个字典，转成列表统一处理
                if isinstance(task_info_list, dict):
                    task_info_list = [task_info_list]

                # 如果 AI 认为没有与当前用户相关的任务，返回了空列表
                if not task_info_list:
                    reply_lines = ["✅ 已收到消息，但未识别到需要您处理的具体任务。"]
                else:
                    reply_lines = [f"✅ 已为您记录 {len(task_info_list)} 个任务:"]

                    for idx, task_info in enumerate(task_info_list, 1):
                        task = await sync_to_async(Task.objects.create)(
                            title=task_info.get('title') or clean_text[:100],
                            description=task_info.get('description') or '',
                            priority=1 if classification == 'urgent' else task_info.get('priority', 2),
                            task_type=task_info.get('task_type', '其他'),
                            source='dingtalk',
                            source_message_id=str(message.id),
                            due_date=task_info.get('due_date'),
                        )

                        priority_display = await sync_to_async(task.get_priority_display)()
                        task_reply = f"{idx}. {task.title} (执行人: {sender_nick})"
                        if task.due_date:
                            task_reply += f' [截止: {task.due_date.strftime("%Y-%m-%d %H:%M")}]'
                        reply_lines.append(task_reply)

                reply = "\n".join(reply_lines)
                if url_infos:
                    new_count = sum(1 for info in url_infos if not info.get("is_existing"))
                    exist_count = len(url_infos) - new_count
                    if new_count > 0 and exist_count > 0:
                        reply += f"\n\n🔗 链接处理完毕（{new_count} 个新保存，{exist_count} 个已存在）："
                    elif new_count > 0:
                        reply += f"\n\n🔗 同时已将 {new_count} 个链接保存到知识库："
                    else:
                        reply += f"\n\n🔗 知识库中已存在该链接："

                    for info in url_infos:
                        status_mark = "🌟" if not info.get("is_existing") else "🔄 已收录"
                        reply += f"\n\n- [{info['category']}] {info['title']} ({status_mark})\n\n   评分：{info['rating']}\n\n   概要：\n\n{info['summary']}"
            elif classification == 'normal' or classification == 'ignore':
                if url_infos:
                    new_count = sum(1 for info in url_infos if not info.get("is_existing"))
                    exist_count = len(url_infos) - new_count

                    if new_count > 0 and exist_count > 0:
                        reply = f"✅ 链接处理完毕（{new_count} 个新保存，{exist_count} 个已存在）："
                    elif new_count > 0:
                        reply = f"✅ 已将 {new_count} 个新链接保存到知识库："
                    else:
                        reply = f"💡 知识库中已存在该链接："

                    for info in url_infos:
                        status_mark = "🌟" if not info.get("is_existing") else "🔄 已收录"
                        reply += f"\n\n [{info['category']}] {info['title']} ({status_mark})\n\n   评分：{info['rating']}\n\n   概要：\n\n{info['summary']}"
                elif not is_group and classification == 'normal':
                    # 只有在单聊且没有提取到链接时，才对普通消息进行回复
                    reply = await sync_to_async(generate_reply)(text)
                else:
                    reply = None
            else:
                reply = None

            if reply:
                self.reply_text(reply, callback)
                await sync_to_async(Message.objects.create)(
                    channel_user=channel_user,
                    platform='dingtalk',
                    content=reply,
                    message_type='text',
                    direction='outbound',
                )

        except Exception:
            logger.exception("处理消息失败")
            try:
                self.reply_text('抱歉，处理消息时出现错误，请稍后重试。', callback)
            except Exception:
                pass

        return AckMessage.STATUS_OK, 'OK'

    def reply_text(self, text: str, callback):
        # 兼容 SDK 差异：有些版本的 callback.data 就是包含 senderStaffId 的字典，但在某些 SDK 的实现里
        # ChatbotHandler 需要将 callback 转型或自己发起 HTTP 请求。这里我们安全地给它包一层对象。
        if not hasattr(callback, 'sender_staff_id'):
            callback.sender_staff_id = callback.data.get('senderStaffId', '')
            callback.session_webhook = callback.data.get('sessionWebhook', '')

        self.reply_markdown('回复', text, callback)
