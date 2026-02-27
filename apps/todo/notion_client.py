import logging
from datetime import datetime

import httpx
from django.conf import settings
from notion_client import Client

logger = logging.getLogger(__name__)

NOTION_API = 'https://api.notion.com/v1'
NOTION_VERSION = '2022-06-28'

PRIORITY_ORDER = {'高': 1, '中': 2, '低': 3}

# Priority mappings from local choices to Notion select options
PRIORITY_MAPPING = {
    1: '高',
    2: '中',
    3: '低',
    4: '低',
}

# Status mappings from local choices to Notion status/select options
STATUS_MAPPING = {
    'pending': '全景时段（排任务、调优先级）',
    'in_progress': '单核时段（当前执行）',
    'done': '已完成',
}

def get_notion_client():
    if not settings.NOTION_API_KEY:
        return None
    return Client(auth=settings.NOTION_API_KEY)


def build_notion_properties(task):
    """
    Build the properties dictionary for Notion API based on Django Task model.
    """
    properties = {
        "任务名称": {
            "title": [
                {
                    "text": {
                        "content": task.title
                    }
                }
            ]
        },
        "描述": {
            "rich_text": [
                {
                    "text": {
                        "content": task.description or ""
                    }
                }
            ]
        },
        "优先级": {
            "select": {
                "name": PRIORITY_MAPPING.get(task.priority, "中")
            }
        },
        "状态": {
            "status": {
                "name": STATUS_MAPPING.get(task.status, "未开始")
            }
        },
        "任务类型": {
            "multi_select": [
                {
                    "name": task.task_type or "其他"
                }
            ]
        }
    }

    if task.due_date:
        # Format datetime to ISO 8601 string for Notion
        properties["截止日期"] = {
            "date": {
                "start": task.due_date.isoformat()
            }
        }

    return properties


def create_page(task):
    """
    Create a new page in the target Notion Database.
    Updates the task's notion_page_id upon success.
    """
    client = get_notion_client()
    if not client or not settings.NOTION_DATABASE_ID:
        logger.warning("Notion API Key or Database ID not configured.")
        return None

    try:
        properties = build_notion_properties(task)
        response = client.pages.create(
            parent={"database_id": settings.NOTION_DATABASE_ID},
            properties=properties
        )
        page_id = response.get("id")
        if page_id:
            # Update the task without triggering save() signals to avoid infinite loop
            from apps.todo.models import Task
            Task.objects.filter(id=task.id).update(notion_page_id=page_id)
            logger.info(f"Successfully created Notion page for Task {task.id}: {page_id}")

            # 如果是刚创建的任务，可以尝试把原始消息补充到 Notion Page 的正文 (Body) 里
            if task.source_message_id:
                from apps.channel.models import Message
                try:
                    msg = Message.objects.get(id=task.source_message_id)
                    children_blocks = []

                    # 如果是图片类型的消息，插入图片块(支持多张图片，逗号分隔)
                    if msg.message_type == 'image':
                        urls = msg.content.split(',')
                        for url in urls:
                            if url.strip():
                                children_blocks.append({
                                    "object": "block",
                                    "type": "image",
                                    "image": {
                                        "type": "external",
                                        "external": {
                                            "url": url.strip()
                                        }
                                    }
                                })
                    else:
                        # 否则作为文本引用块插入
                        children_blocks.append({
                            "object": "block",
                            "type": "quote",
                            "quote": {
                                "rich_text": [
                                    {
                                        "type": "text",
                                        "text": {
                                            "content": msg.content[:2000] # 限制长度避免超出 Notion 限制
                                        }
                                    }
                                ]
                            }
                        })

                    client.blocks.children.append(
                        block_id=page_id,
                        children=children_blocks
                    )
                except Exception as e:
                    logger.warning(f"Failed to append original message to Notion page {page_id}: {e}")

            return page_id
    except Exception as e:
        logger.error(f"Failed to create Notion page for Task {task.id}: {e}")
        return None


def update_page(task):
    """
    Update an existing page in Notion based on the task's notion_page_id.
    """
    client = get_notion_client()
    if not client or not task.notion_page_id:
        return None

    try:
        properties = build_notion_properties(task)
        response = client.pages.update(
            page_id=task.notion_page_id,
            properties=properties
        )
        logger.info(f"Successfully updated Notion page for Task {task.id}: {task.notion_page_id}")
        return response.get("id")
    except Exception as e:
        logger.error(f"Failed to update Notion page for Task {task.id}: {e}")
        return None


def sync_task_to_notion(task_id):
    """
    Main entry point for syncing a task to Notion. Intended to be run in a background thread.
    """
    from apps.todo.models import Task
    try:
        task = Task.objects.get(id=task_id)
        if task.notion_page_id:
            update_page(task)
        else:
            create_page(task)
    except Task.DoesNotExist:
        logger.error(f"Task with id {task_id} not found during Notion sync.")
    except Exception as e:
        logger.exception(f"Unexpected error during Notion sync for Task {task_id}: {e}")


# ---- Notion 查询 ----

def _notion_headers():
    return {
        'Authorization': f'Bearer {settings.NOTION_API_KEY}',
        'Notion-Version': NOTION_VERSION,
        'Content-Type': 'application/json',
    }


def _parse_page(page: dict) -> dict:
    """将 Notion page 解析为简单字典。"""
    props = page.get('properties', {})

    title_parts = props.get('任务名称', {}).get('title', [])
    title = ''.join(t.get('plain_text', '') for t in title_parts)

    desc_parts = props.get('描述', {}).get('rich_text', [])
    description = ''.join(t.get('plain_text', '') for t in desc_parts)

    status = props.get('状态', {}).get('status', {}).get('name', '')
    priority_name = (props.get('优先级', {}).get('select') or {}).get('name', '中')
    priority = PRIORITY_ORDER.get(priority_name, 2)

    type_items = props.get('任务类型', {}).get('multi_select', [])
    task_type = ', '.join(t.get('name', '') for t in type_items) or '其他'

    due_date_raw = (props.get('截止日期', {}).get('date') or {}).get('start')
    due_date = None
    if due_date_raw:
        try:
            due_date = datetime.fromisoformat(due_date_raw)
        except (ValueError, TypeError):
            pass

    return {
        'title': title,
        'description': description,
        'status': status,
        'priority': priority,
        'priority_name': priority_name,
        'task_type': task_type,
        'due_date': due_date,
        'page_id': page.get('id', ''),
    }


def query_notion_tasks(filter_body: dict | None = None) -> list[dict]:
    """查询 Notion 数据库，返回解析后的任务列表。"""
    if not settings.NOTION_API_KEY or not settings.NOTION_DATABASE_ID:
        logger.warning("Notion 未配置，跳过查询")
        return []

    try:
        body = {'page_size': 100}
        if filter_body:
            body['filter'] = filter_body

        resp = httpx.post(
            f'{NOTION_API}/databases/{settings.NOTION_DATABASE_ID}/query',
            headers=_notion_headers(),
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return [_parse_page(p) for p in data.get('results', [])]
    except Exception:
        logger.exception("查询 Notion 数据库失败")
        return []


def query_incomplete_tasks() -> list[dict]:
    """查询所有未完成的任务（状态 != 已完成）。"""
    return query_notion_tasks(
        filter_body={
            'property': '状态',
            'status': {'does_not_equal': '已完成'},
        }
    )


def query_last_week_completed_tasks() -> list[dict]:
    """查询上周完成的任务。基于状态为'已完成'且最后编辑时间在上周的逻辑。"""
    from django.utils import timezone
    from datetime import timedelta

    now = timezone.now()
    # 计算上周一的零点
    days_since_monday = now.weekday()
    last_monday = (now - timedelta(days=days_since_monday + 7)).replace(hour=0, minute=0, second=0, microsecond=0)
    # 计算本周一的零点（即上周日的23:59:59之后）
    this_monday = last_monday + timedelta(days=7)

    return query_notion_tasks(
        filter_body={
            "and": [
                {
                    "property": "状态",
                    "status": {
                        "equals": "已完成"
                    }
                },
                {
                    "timestamp": "last_edited_time",
                    "last_edited_time": {
                        "on_or_after": last_monday.isoformat()
                    }
                },
                {
                    "timestamp": "last_edited_time",
                    "last_edited_time": {
                        "before": this_monday.isoformat()
                    }
                }
            ]
        }
    )

def check_link_exists_in_knowledge_base(url):
    """
    Check if a given URL already exists in the Knowledge Base database.
    Returns a dictionary with existing page info if found, otherwise None.
    """
    kb_db_id = settings.NOTION_KB_DATABASE_ID
    if not settings.NOTION_API_KEY or not kb_db_id:
        return None

    try:
        body = {
            "filter": {
                "property": "URL",
                "url": {
                    "equals": url
                }
            },
            "page_size": 1
        }

        resp = httpx.post(
            f'{NOTION_API}/databases/{kb_db_id}/query',
            headers=_notion_headers(),
            json=body,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get('results', [])

        if results:
            # 获取已经存在的记录信息返回
            page = results[0]
            props = page.get('properties', {})

            title_prop = props.get('标题', {}).get('title', [])
            title = title_prop[0]['text']['content'] if title_prop else url

            category = props.get('分类', {}).get('select', {}).get('name', '其他') if props.get('分类', {}).get('select') else '其他'
            rating = props.get('评分', {}).get('select', {}).get('name', '⭐⭐⭐') if props.get('评分', {}).get('select') else '⭐⭐⭐'

            summary_prop = props.get('概要', {}).get('rich_text', [])
            summary = summary_prop[0]['text']['content'] if summary_prop else '暂无摘要'

            return {
                "exists": True,
                "title": title,
                "category": category,
                "rating": rating,
                "summary": summary
            }
        return None
    except Exception as e:
        logger.error(f"Failed to query Notion KB for URL {url}: {e}")
        return None


def save_link_to_knowledge_base(url, title, source_name, category, publish_date=None, rating="⭐⭐⭐", summary=""):
    """
    Save extracted URL to a dedicated Notion Knowledge Base database.
    """
    client = get_notion_client()
    kb_db_id = settings.NOTION_KB_DATABASE_ID

    if not client or not kb_db_id:
        logger.warning("Notion API Key or KB Database ID not configured. Skipping saving link.")
        return None

    try:
        properties = {
            "标题": {
                "title": [
                    {
                        "text": {
                            "content": title
                        }
                    }
                ]
            },
            "URL": {
                "url": url
            },
            "来源": {
                "rich_text": [
                    {
                        "text": {
                            "content": source_name
                        }
                    }
                ]
            },
            "概要": {
                "rich_text": [
                    {
                        "text": {
                            "content": summary
                        }
                    }
                ]
            },
            "状态": {
                "status": {
                    "name": "未阅读"
                }
            },
            "分类": {
                "select": {
                    "name": category
                }
            },
            "评分": {
                "select": {
                    "name": rating
                }
            }
        }

        if publish_date:
            properties["日期"] = {
                "date": {
                    "start": publish_date
                }
            }
        # 如果没有获取到 publish_date，直接留空（不添加"日期"属性），不再使用当前时间兜底

        response = client.pages.create(
            parent={"database_id": kb_db_id},
            properties=properties
        )
        page_id = response.get("id")
        logger.info(f"Successfully created Notion KB page for URL {url}: {page_id}")
        return page_id
    except Exception as e:
        logger.error(f"Failed to save URL {url} to Notion KB: {e}")
        return None
