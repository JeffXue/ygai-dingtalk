import asyncio
import httpx
import re
import os
import json

# 手动读取 .env
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, val = line.split('=', 1)
                os.environ[key] = val

async def test_xhs():
    # 测试有复杂参数的链接
    url = "https://www.xiaohongshu.com/explore/69c1448d000000002102d55d?app_platform=android&ignoreEngage=true&app_version=9.23.0&share_from_user_hidden=true&xsec_source=app_share&type=video&xsec_token=CB4waLK0fUHyt3Fe8rLm8hvZQCK8chebAUaHv02hngwQw=&author_share=1&xhsshare=&shareRedId=OD9DM0RKO0E2NzUyOTgwNjg3OThGRjg_&apptime=1774884844&share_id=e9169d7ac1bc45d9b607dad5b1f4a995&share_channel=wechat&wechatWid=67e12627c577421fc1e3517dbbb60d82&wechatOrigin=menu"

    xhs_cookie = os.environ.get('XIAOHONGSHU_COOKIE', '')
    if not xhs_cookie:
        print("未找到 XIAOHONGSHU_COOKIE！")
        return

    xhs_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Cookie': xhs_cookie
    }

    # 测试不同提取方式的URL
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)

    # 1. 完全去除参数 (目前线上的做法)
    pure_url = url.split('?')[0]

    # 2. 保留全部参数 (之前失败的做法)
    full_url = url

    # 3. 仅保留 xsec_token 和 xsec_source (针对小红书某些强控分享链接的做法)
    keep_qs = {}
    if 'xsec_token' in qs:
        keep_qs['xsec_token'] = qs['xsec_token'][0]
    if 'xsec_source' in qs:
        keep_qs['xsec_source'] = qs['xsec_source'][0]
    safe_url = pure_url + "?" + urllib.parse.urlencode(keep_qs) if keep_qs else pure_url

    urls_to_test = {
        "原链接(带Wechat等追踪)": full_url,
        "全去除(无参数)": pure_url,
        "仅保留xsec验证参数": safe_url
    }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for name, test_url in urls_to_test.items():
            print(f"\n=== 测试: {name} ===")
            print(f"URL: {test_url}")
            response = await client.get(test_url, headers=xhs_headers)
            print(f"Status Code: {response.status_code}")

            match = re.search(r'window\.__INITIAL_STATE__=({.*?})</script>', response.text)
            if match:
                json_str = match.group(1).replace('undefined', 'null')
                try:
                    data = json.loads(json_str)
                    note_details = data.get('note', {}).get('noteDetailMap', {})
                    if note_details and 'null' not in note_details.keys():
                        first_key = list(note_details.keys())[0]
                        note_info = note_details[first_key].get('note', {})
                        title = note_info.get('title', '')
                        desc = note_info.get('desc', '')
                        print(f"成功获取: title={title}, desc={desc[:20]}...")
                    else:
                        print("有 __INITIAL_STATE__ 但 noteDetailMap 为空或 null")
                except json.JSONDecodeError as e:
                    print(f"JSON解析失败: {e}")
            else:
                print("没找到 __INITIAL_STATE__。可能被拦截。")

if __name__ == "__main__":
    asyncio.run(test_xhs())
