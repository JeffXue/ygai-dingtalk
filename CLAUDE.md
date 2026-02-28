# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build and Run Commands
The system consists of two independent processes that must run simultaneously:

*   **Django Web Server (Backend & API):**
    ```bash
    python manage.py runserver 0.0.0.0:8000
    ```
*   **DingTalk Stream Bot & Scheduler:**
    ```bash
    ./start_dingtalk_bot.sh
    # Alternatively: python manage.py run_dingtalk_bot
    ```
*   **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
*(Note: There are currently no automated test coverage or linting commands configured for this project.)*

## Architecture & Data Flow
YGAI is an AI-driven personal productivity assistant built on **Django 5.1**, integrating **DingTalk** (via WebSocket Stream mode, no public IP needed), **Alibaba Qianwen LLM** (DashScope), and **Notion API**.

### App Structure (`apps/`)
*   `channel/`: Handles DingTalk WebSocket connection, message receiving/sending, URL regex extraction, and async web crawling (`httpx` + `BeautifulSoup4`).
*   `ai/`: Core LLM logic invoking DashScope (`qwen-plus`/`qwen-max`). Contains `classifier.py` (intent routing), `extractor.py` (task entity extraction), `responder.py` (auto-reply), and article summarizers.
*   `todo/`: Manages Todo and Knowledge Base models, Notion API synchronization (`notion-client`), and background scheduled jobs (`scheduler.py` via `APScheduler`).

### Message Workflow
1.  **Ingestion:** DingTalk Bot receives via WebSocket.
2.  **Processing:**
    *   If URL is present: Check Notion KB for duplicates $\rightarrow$ Crawl $\rightarrow$ AI scoring/summary $\rightarrow$ Write to Notion KB.
    *   AI Classifier routes message intent:
        *   `urgent/important`: AI extracts task details $\rightarrow$ Write to Notion Task DB.
        *   `normal`: AI generates response $\rightarrow$ Send to DingTalk.
        *   `ignore`: Silently archive.

## Environment & Configuration
Configuration requires `.env` (via `django-environ`). Critical required variables:
*   `DINGTALK_APP_KEY`, `DINGTALK_APP_SECRET`, `DINGTALK_NOTIFY_USER_ID`
*   `DASHSCOPE_API_KEY`
*   `NOTION_API_KEY`, `NOTION_DATABASE_ID` (Tasks), `NOTION_KB_DATABASE_ID` (Articles)

### Critical External Dependencies (Notion Schemas)
For Notion DB writes to succeed, the target databases must strictly map to these column names and types:
*   **Task DB:** 任务名称 (Title), 描述 (Rich text), 优先级 (Select), 状态 (Status), 任务类型 (Multi-select), 截止日期 (Date).
*   **Knowledge Base DB:** 标题 (Title), URL, 来源 (Rich text), 概要 (Rich text), 状态 (Status, needs `未阅读`), 分类 (Select), 评分 (Select, needs ⭐ to ⭐⭐⭐⭐⭐), 日期 (Date).

### Background Jobs (APScheduler)
*   **Weekly Tasks:** Mon 09:00
*   **Daily Priorities:** Weekdays 09:00 (except Mon)
*   **Deadline Reminders:** Daily 18:00
*   **Last Week Summary:** Mon 17:00
