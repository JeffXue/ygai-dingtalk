import logging
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from datetime import datetime

logger = logging.getLogger(__name__)

def parse_url_metadata(url: str) -> dict:
    """
    Fetch URL and extract metadata: title, date, source_name
    """
    metadata = {
        "title": None,
        "date": None,
        "source_name": None
    }

    # 1. Determine source name from URL
    try:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.lower()
        if 'mp.weixin.qq.com' in domain:
            metadata['source_name'] = '公众号'
        elif 'xiaohongshu.com' in domain:
            metadata['source_name'] = '小红书'
        elif 'douyin.com' in domain:
            metadata['source_name'] = '抖音'
        elif 'juejin.cn' in domain:
            metadata['source_name'] = '掘金'
        elif 'csdn.net' in domain:
            metadata['source_name'] = 'CSDN'
        else:
            metadata['source_name'] = domain
    except Exception as e:
        logger.warning(f"Failed to parse domain from url {url}: {e}")

    # 2. Fetch HTML content
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        # Disable verify for some strict sites, use a short timeout
        response = httpx.get(url, headers=headers, follow_redirects=True, timeout=10.0, verify=False)
        response.raise_for_status()
        html = response.text

        soup = BeautifulSoup(html, 'lxml')

        # Extract title
        if soup.title and soup.title.string:
            metadata['title'] = soup.title.string.strip()

        # Extract date from meta tags
        date_str = None
        meta_published_time = soup.find('meta', property='article:published_time')
        if meta_published_time and meta_published_time.get('content'):
            date_str = meta_published_time.get('content')
        else:
            meta_pubdate = soup.find('meta', attrs={'name': 'pubdate'})
            if meta_pubdate and meta_pubdate.get('content'):
                date_str = meta_pubdate.get('content')

        if date_str:
            try:
                # Try to parse standard ISO format or similar
                # Notion Date property accepts ISO 8601 strings
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                metadata['date'] = dt.isoformat()
            except Exception:
                # If parsing fails, just leave it as None to fallback to current time
                pass

    except Exception as e:
        logger.warning(f"Failed to fetch or parse URL {url}: {e}")

    return metadata
