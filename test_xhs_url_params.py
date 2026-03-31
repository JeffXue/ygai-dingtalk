import httpx
import re
import json

url = "https://www.xiaohongshu.com/explore/69c1448d000000002102d55d?app_platform=android&ignoreEngage=true&app_version=9.23.0&share_from_user_hidden=true&xsec_source=app_share&type=video&xsec_token=CB4waLK0fUHyt3Fe8rLm8hvZQCK8chebAUaHv02hngwQw=&author_share=1&xhsshare=&shareRedId=OD9DM0RKO0E2NzUyOTgwNjg3OThGRjg_&apptime=1774884844&share_id=e9169d7ac1bc45d9b607dad5b1f4a995&share_channel=wechat&wechatWid=67e12627c577421fc1e3517dbbb60d82&wechatOrigin=menu"
cookie_str = "abRequestId=d72a0370-dd4d-5441-97f6-7bcace6b428b; a1=19b5862c7f92gf9d6a1st9wiopril3uz13xuhpxm830000390386; webId=080ab91a1700575139dba2d4770f01d3; gid=yjD2YKJfY2yqyjD2YKJSWqUCijJkijfK0yM9C6YjE3lUF7q831q7ux888qj8qYK8yWYWDyWJ; id_token=VjEAAHeUpC0TN71aiLS7l68wk9nWaXEozk9GmOYnSWgV2Gx5WiyMNQr3jWzVC76HFTd1U0PdD/bxwAfcDC0tguNL/hEGU8jCXXAusGpBHbZJxk/7m8ltDsa0ELPDlDWiDvbcl4pM; web_session=030037ae7eb84fc808fb4d7ede2e4a429dfc3c; ets=1774836105049; webBuild=6.2.3; unread={%22ub%22:%2269b4d52f000000001a02234b%22%2C%22ue%22:%2269c3a45c0000000021012717%22%2C%22uc%22:61}; acw_tc=0a0d0d6817749223842737765e6030b2cac833655d115c3d879928be870abe; xsecappid=ugc; websectiga=f47eda31ec99545da40c2f731f0630efd2b0959e1dd10d5fedac3dce0bd1e04d; sec_poison_id=c84d2acf-4e69-4a6c-9683-0b5b47b3eb9d; customer-sso-sid=68c517623236452831657986kazgjhwvddojjark; x-user-id-creator.xiaohongshu.com=5cebfaa8000000001100d527; customerClientId=907331368676599; access-token-creator.xiaohongshu.com=customer.creator.AT-68c517623236452831674376cm8o6llozvskdsu6; galaxy_creator_session_id=fGN5gFVaQGChPIZ5QeXa72eJZkYhMScECOXS; galaxy.creator.beaker.session.id=1774923050183056433798; loadts=1774923122193"

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
    'Cookie': cookie_str
}
response = httpx.get(url, headers=headers)
html = response.text

match = re.search(r'window\.__INITIAL_STATE__=({.*?})</script>', html)
if match:
    json_str = match.group(1).replace('undefined', 'null')
    data = json.loads(json_str)
    note_details = data.get('note', {}).get('noteDetailMap', {})
    
    first_key = list(note_details.keys())[0] if note_details else None
    if first_key and 'null' not in note_details:
        print("Success!", note_details[first_key].get('note', {}).get('title'))
    else:
        print("Failed. Available keys:", note_details.keys())
        first_key = list(note_details.keys())[0] if note_details else None
        if first_key:
            print("Content:", json.dumps(note_details[first_key], ensure_ascii=False)[:300])
