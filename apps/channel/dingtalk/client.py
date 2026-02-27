import logging
import time

import httpx
from django.conf import settings

logger = logging.getLogger(__name__)

OPENAPI_ENDPOINT = 'https://api.dingtalk.com'

_access_token_cache = {
    'token': '',
    'expires_at': 0,
}


def get_access_token() -> str:
    """获取新版 API 的 access_token（v1.0/oauth2/accessToken）。"""
    now = time.time()
    if _access_token_cache['token'] and _access_token_cache['expires_at'] > now:
        return _access_token_cache['token']

    resp = httpx.post(
        f'{OPENAPI_ENDPOINT}/v1.0/oauth2/accessToken',
        json={
            'appKey': settings.DINGTALK_APP_KEY,
            'appSecret': settings.DINGTALK_APP_SECRET,
        },
    )
    resp.raise_for_status()
    data = resp.json()

    token = data.get('accessToken')
    if not token:
        raise RuntimeError(f"Failed to get DingTalk access token: {data}")

    _access_token_cache['token'] = token
    _access_token_cache['expires_at'] = now + data.get('expireIn', 7200) - 60
    return token


def send_message(content: str, user_ids: list[str] | str | None = None) -> dict:
    """通过机器人 BatchSendOTO 接口发送单聊消息。"""
    token = get_access_token()
    if user_ids is None:
        user_ids = getattr(settings, 'DINGTALK_NOTIFY_USER_ID', '')
    if isinstance(user_ids, str):
        user_ids = [user_ids]

    import json
    resp = httpx.post(
        f'{OPENAPI_ENDPOINT}/v1.0/robot/oToMessages/batchSend',
        headers={'x-acs-dingtalk-access-token': token},
        json={
            'robotCode': settings.DINGTALK_APP_KEY,
            'userIds': user_ids,
            'msgKey': 'sampleText',
            'msgParam': json.dumps({'content': content}),
        },
    )
    resp.raise_for_status()
    return resp.json()


def get_user_info(user_id: str) -> dict:
    token = get_access_token()
    resp = httpx.get(
        f'{OPENAPI_ENDPOINT}/v1.0/contact/users/{user_id}',
        headers={'x-acs-dingtalk-access-token': token},
    )
    if resp.status_code != 200:
        logger.warning("Failed to get user info for %s: %s", user_id, resp.text)
        return {}
    return resp.json()
