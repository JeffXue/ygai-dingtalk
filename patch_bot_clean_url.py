import re

with open("apps/channel/dingtalk/bot.py", "r", encoding="utf-8") as f:
    code = f.read()

old_block = """\
                            try:
                                # 注意！！！客户端本身可能自带了全局 header，我们用全新的独立的客户端去请求
                                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as isolated_client:
                                    xhs_response = await isolated_client.get(url, headers=xhs_headers)
"""

new_block = """\
                            try:
                                # 极其重要：清洗掉分享链接带来的所有身份追踪后缀，否则在加上电脑端Cookie时会触发后端环境身份不一致风控
                                pure_url = url.split('?')[0]
                                
                                # 注意！！！客户端本身可能自带了全局 header，我们用全新的独立的客户端去请求
                                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as isolated_client:
                                    xhs_response = await isolated_client.get(pure_url, headers=xhs_headers)
"""

if old_block in code:
    with open("apps/channel/dingtalk/bot.py", "w", encoding="utf-8") as f:
        f.write(code.replace(old_block, new_block))
    print("Patch applied successfully.")
else:
    print("Old block not found!")
