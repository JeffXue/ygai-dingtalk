import httpx
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

async def get_dingtalk_access_token():
    """获取钉钉 OpenAPI 的 access_token"""
    url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
    payload = {
        "appKey": settings.DINGTALK_APP_KEY,
        "appSecret": settings.DINGTALK_APP_SECRET
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("accessToken")
        except Exception as e:
            logger.error(f"Failed to get DingTalk access token: {e}")
            return None

async def get_download_url(download_code, robot_code):
    """通过 downloadCode 换取真实的临时下载链接"""
    token = await get_dingtalk_access_token()
    if not token:
        logger.error("No access token available for DingTalk API.")
        return None

    url = "https://api.dingtalk.com/v1.0/robot/messageFiles/download"
    headers = {
        "x-acs-dingtalk-access-token": token,
        "Content-Type": "application/json"
    }
    payload = {
        "downloadCode": download_code,
        "robotCode": robot_code
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("downloadUrl")
        except Exception as e:
            logger.error(f"Failed to get download URL from DingTalk: {e}")
            return None