import logging
from datetime import datetime, timedelta
from http import HTTPStatus

import dashscope
from dashscope import Generation
from django.conf import settings
from django.utils import timezone

from apps.todo.notion_client import query_incomplete_tasks, query_last_week_completed_tasks, query_notion_tasks
from apps.channel.dingtalk.client import send_message

logger = logging.getLogger(__name__)


def _call_ai(prompt: str) -> str:
    """调用 qwen-max 生成摘要文本。"""
    if not settings.DASHSCOPE_API_KEY:
        logger.warning("DASHSCOPE_API_KEY 未配置，跳过 AI 摘要")
        return ''

    dashscope.api_key = settings.DASHSCOPE_API_KEY
    response = Generation.call(
        model='qwen-max',
        messages=[{'role': 'user', 'content': prompt}],
        result_format='message',
    )
    if response.status_code == HTTPStatus.OK:
        return response.output.choices[0].message.content.strip()
    logger.error("AI 摘要失败: %s - %s", response.code, response.message)
    return ''


def _format_task_list(tasks: list[dict]) -> str:
    """将 Notion 任务字典列表格式化为文本。"""
    lines = []
    for t in tasks:
        due = t['due_date'].strftime('%m/%d') if t.get('due_date') else '无截止'
        lines.append(f"- [{t['priority_name']}] {t['title']}（{t['status']}，截止: {due}）")
    return '\n'.join(lines)


def _notify(content: str):
    """发送钉钉通知给配置的用户。"""
    user_id = getattr(settings, 'DINGTALK_NOTIFY_USER_ID', '')
    if not user_id:
        logger.warning("DINGTALK_NOTIFY_USER_ID 未配置，跳过通知")
        return
    try:
        send_message(content, user_ids=user_id)
        logger.info("通知已发送")
    except Exception:
        logger.exception("发送钉钉通知失败")


def generate_weekly_summary(tasks: list[dict]) -> str:
    task_text = _format_task_list(tasks)
    prompt = (
        "你是一个项目管理助手。以下是当前所有未完成的任务列表：\n"
        f"{task_text}\n\n"
        "请从中提炼出本周最核心的 5 个事项，按优先级排序，"
        "用简洁的中文列表输出，每项不超过 30 字。"
        "最后用一句话总结本周工作重点。"
    )
    return _call_ai(prompt)


def generate_daily_summary(tasks: list[dict]) -> str:
    task_text = _format_task_list(tasks)
    prompt = (
        "你是一个项目管理助手。以下是当前所有未完成的任务列表：\n"
        f"{task_text}\n\n"
        "请从中选出今天最重要的 2 个事项，用简洁的中文说明"
        "为什么它们最重要以及建议如何推进，每项不超过 50 字。"
    )
    return _call_ai(prompt)


def generate_due_advice(tasks: list[dict]) -> str:
    task_text = _format_task_list(tasks)
    now_str = timezone.localtime().strftime('%Y-%m-%d %H:%M')
    prompt = (
        f"当前时间: {now_str}\n"
        "你是一个项目管理助手。以下任务即将到期或已过期：\n"
        f"{task_text}\n\n"
        "请针对每个任务给出简短的处理建议（如：立即处理、申请延期、委派他人等），"
        "每项不超过 30 字。"
    )
    return _call_ai(prompt)


def generate_last_week_summary(tasks: list[dict]) -> str:
    task_text = _format_task_list(tasks)
    prompt = (
        "你是一个项目管理助手。以下是用户在上周完成的工作任务列表：\n"
        f"{task_text}\n\n"
        "请帮用户写一份简洁专业的工作总结（适合用于周报）。\n"
        "要求：\n"
        "1. 按任务类型或重要程度分类汇总\n"
        "2. 突出核心产出和价值\n"
        "3. 总字数控制在 200-300 字以内"
    )
    return _call_ai(prompt)


# ---- 定时任务 ----

def weekly_report_job():
    """每周一 9:00 — 周报摘要。"""
    logger.info("执行周报任务...")
    tasks = query_incomplete_tasks()
    if not tasks:
        _notify("📋 周报：当前没有未完成任务，本周可以轻松一些！")
        return
    summary = generate_weekly_summary(tasks)
    if summary:
        _notify(f"📋 每周工作摘要\n\n{summary}")
    else:
        _notify(f"📋 每周工作摘要\n\n{_format_task_list(tasks)}")


def daily_top_tasks_job():
    """每个工作日 9:00（周一除外）— 每日要事。"""
    now = timezone.localtime()
    if now.weekday() == 0:
        return
    logger.info("执行每日要事任务...")
    tasks = query_incomplete_tasks()
    if not tasks:
        return
    # 按优先级排序
    tasks.sort(key=lambda t: t['priority'])
    summary = generate_daily_summary(tasks)
    if summary:
        _notify(f"🌅 今日要事\n\n{summary}")
    else:
        _notify(f"🌅 今日要事\n\n{_format_task_list(tasks[:2])}")


def due_date_check_job():
    """每小时执行 — 检查到期/即将到期任务。"""
    logger.info("执行到期检查任务...")
    tasks = query_incomplete_tasks()
    if not tasks:
        return

    now = datetime.now()
    deadline = now + timedelta(hours=24)

    # 筛选有截止日期且在 24h 内到期或已过期的任务（统一为 naive 比较）
    def _naive(dt):
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    due_tasks = [t for t in tasks if t.get('due_date') and _naive(t['due_date']) <= deadline]
    if not due_tasks:
        return

    overdue = [t for t in due_tasks if _naive(t['due_date']) <= now]
    upcoming = [t for t in due_tasks if _naive(t['due_date']) > now]

    parts = []
    if overdue:
        parts.append(f"⚠️ 已过期 ({len(overdue)}):\n{_format_task_list(overdue)}")
    if upcoming:
        parts.append(f"⏰ 24h 内到期 ({len(upcoming)}):\n{_format_task_list(upcoming)}")
    task_text = '\n\n'.join(parts)

    advice = generate_due_advice(due_tasks)
    if advice:
        _notify(f"🔔 到期提醒\n\n{task_text}\n\n💡 建议:\n{advice}")
    else:
        _notify(f"🔔 到期提醒\n\n{task_text}")


def last_week_summary_job():
    """每周一 17:00 — 上周工作总结。"""
    logger.info("执行上周工作总结任务...")
    tasks = query_last_week_completed_tasks()
    if not tasks:
        _notify("📝 上周工作总结：上周暂无记录的已完成任务。")
        return

    summary = generate_last_week_summary(tasks)
    if summary:
        _notify(f"📝 上周工作总结 (共完成 {len(tasks)} 项)\n\n{summary}")
    else:
        _notify(f"📝 上周工作总结 (共完成 {len(tasks)} 项)\n\n{_format_task_list(tasks)}")


# ---- 调度器 ----

def start_scheduler():
    """初始化 APScheduler 并注册定时任务。"""
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BackgroundScheduler(timezone='Asia/Shanghai')

    # 每周一 9:00
    scheduler.add_job(
        weekly_report_job,
        CronTrigger(day_of_week='mon', hour=9, minute=0),
        id='weekly_report',
        replace_existing=True,
    )

    # 工作日（周一到周五）9:00
    scheduler.add_job(
        daily_top_tasks_job,
        CronTrigger(day_of_week='mon-fri', hour=9, minute=0),
        id='daily_top_tasks',
        replace_existing=True,
    )

    # 每周一 17:00
    scheduler.add_job(
        last_week_summary_job,
        CronTrigger(day_of_week='mon', hour=17, minute=0),
        id='last_week_summary',
        replace_existing=True,
    )

    # 每天 18:00
    scheduler.add_job(
        due_date_check_job,
        CronTrigger(hour=18, minute=0),
        id='due_date_check',
        replace_existing=True,
    )

    scheduler.start()
    logger.info("APScheduler 已启动，注册了 %d 个定时任务", len(scheduler.get_jobs()))
