"""
多种数据抓取器实现
支持多种方式获取 Notion 数据，实现降级策略
"""
from abc import ABC, abstractmethod
from typing import Optional
from rich.console import Console

console = Console()


class BaseScraper(ABC):
    """抓取器基类"""

    @abstractmethod
    def scrape(self, url: str) -> Optional[str]:
        """
        抓取数据

        Args:
            url: 数据源URL

        Returns:
            抓取到的原始文本，失败返回 None
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取抓取器名称"""
        pass


class FirecrawlAPIScraper(BaseScraper):
    """Firecrawl API 抓取器"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def scrape(self, url: str) -> Optional[str]:
        """使用 Firecrawl API 抓取数据"""
        try:
            import requests

            console.print(f"[dim]使用 {self.get_name()} 抓取数据...[/dim]")

            # 调用 Firecrawl API
            api_url = "https://api.firecrawl.dev/v1/scrape"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "url": url,
                "formats": ["markdown"]
            }

            response = requests.post(api_url, json=payload, headers=headers, timeout=120)

            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'markdown' in data['data']:
                    console.print(f"[green]✓[/green] {self.get_name()} 抓取成功")
                    return data['data']['markdown']

            console.print(f"[yellow]✗ {self.get_name()} 抓取失败: HTTP {response.status_code}[/yellow]")
            return None

        except ImportError:
            console.print(f"[yellow]✗ {self.get_name()} 不可用: 缺少 requests 库[/yellow]")
            console.print("[dim]安装: pip install requests[/dim]")
            return None
        except Exception as e:
            console.print(f"[yellow]✗ {self.get_name()} 抓取失败: {e}[/yellow]")
            return None

    def get_name(self) -> str:
        return "Firecrawl API"


class NotionAPIScraper(BaseScraper):
    """Notion 官方 API 抓取器"""

    def __init__(self, api_token: str):
        self.api_token = api_token

    def scrape(self, url: str) -> Optional[str]:
        """使用 Notion API 抓取数据"""
        try:
            from notion_client import Client

            console.print(f"[dim]使用 {self.get_name()} 抓取数据...[/dim]")

            # 从 URL 提取 page_id
            page_id = self._extract_page_id(url)
            if not page_id:
                console.print(f"[yellow]✗ {self.get_name()} 失败: 无法从URL提取 page_id[/yellow]")
                return None

            # 初始化 Notion 客户端
            notion = Client(auth=self.api_token)

            # 获取页面内容
            page = notion.pages.retrieve(page_id=page_id)
            blocks = notion.blocks.children.list(block_id=page_id)

            # 转换为文本
            text = self._blocks_to_text(blocks['results'])

            if text:
                console.print(f"[green]✓[/green] {self.get_name()} 抓取成功")
                return text

            console.print(f"[yellow]✗ {self.get_name()} 抓取失败: 页面为空[/yellow]")
            return None

        except ImportError:
            console.print(f"[yellow]✗ {self.get_name()} 不可用: 缺少 notion-client 库[/yellow]")
            console.print("[dim]安装: pip install notion-client[/dim]")
            return None
        except Exception as e:
            console.print(f"[yellow]✗ {self.get_name()} 抓取失败: {e}[/yellow]")
            return None

    def _extract_page_id(self, url: str) -> Optional[str]:
        """从 Notion URL 提取 page_id"""
        # Notion URL 格式: https://www.notion.so/Title-{page_id}
        # 或: https://www.notion.so/{page_id}
        import re
        match = re.search(r'([a-f0-9]{32})', url)
        if match:
            page_id = match.group(1)
            # 添加连字符
            return f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"
        return None

    def _blocks_to_text(self, blocks: list) -> str:
        """将 Notion blocks 转换为文本"""
        text_parts = []

        for block in blocks:
            block_type = block.get('type')

            if block_type == 'paragraph':
                text_parts.append(self._extract_rich_text(block['paragraph']['rich_text']))
            elif block_type == 'heading_1':
                text_parts.append(f"# {self._extract_rich_text(block['heading_1']['rich_text'])}")
            elif block_type == 'heading_2':
                text_parts.append(f"## {self._extract_rich_text(block['heading_2']['rich_text'])}")
            elif block_type == 'heading_3':
                text_parts.append(f"### {self._extract_rich_text(block['heading_3']['rich_text'])}")
            elif block_type == 'bulleted_list_item':
                text_parts.append(f"- {self._extract_rich_text(block['bulleted_list_item']['rich_text'])}")
            elif block_type == 'numbered_list_item':
                text_parts.append(f"1. {self._extract_rich_text(block['numbered_list_item']['rich_text'])}")

        return '\n'.join(text_parts)

    def _extract_rich_text(self, rich_text: list) -> str:
        """提取 rich_text 中的纯文本"""
        return ''.join([item['plain_text'] for item in rich_text])

    def get_name(self) -> str:
        return "Notion API"


class SimpleHTTPScraper(BaseScraper):
    """简单 HTTP 请求抓取器（适用于公开页面）"""

    def scrape(self, url: str) -> Optional[str]:
        """使用简单 HTTP 请求抓取数据"""
        try:
            import requests
            from bs4 import BeautifulSoup

            console.print(f"[dim]使用 {self.get_name()} 抓取数据...[/dim]")

            # 发送请求
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=120)

            if response.status_code != 200:
                console.print(f"[yellow]✗ {self.get_name()} 抓取失败: HTTP {response.status_code}[/yellow]")
                return None

            # 解析 HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # 尝试找到主要内容区域
            # Notion 的公开页面通常内容在特定的 div 中
            content_div = soup.find('div', class_='notion-page-content')
            if not content_div:
                # 尝试其他可能的容器
                content_div = soup.find('article') or soup.find('main') or soup.body

            if content_div:
                # 提取文本
                text = content_div.get_text(separator='\n', strip=True)
                if text:
                    console.print(f"[green]✓[/green] {self.get_name()} 抓取成功")
                    return text

            console.print(f"[yellow]✗ {self.get_name()} 抓取失败: 未找到内容[/yellow]")
            return None

        except ImportError:
            console.print(f"[yellow]✗ {self.get_name()} 不可用: 缺少依赖库[/yellow]")
            console.print("[dim]安装: pip install requests beautifulsoup4[/dim]")
            return None
        except Exception as e:
            console.print(f"[yellow]✗ {self.get_name()} 抓取失败: {e}[/yellow]")
            return None

    def get_name(self) -> str:
        return "简单HTTP请求"


class TestDataScraper(BaseScraper):
    """测试数据抓取器（最后降级）"""

    def scrape(self, url: str) -> Optional[str]:
        """返回测试数据"""
        console.print(f"[yellow]使用 {self.get_name()}[/yellow]")

        # 返回测试数据
        return """10.14

Btc  场外指数682场外退场期第4天

爆破指数31

谢林点 110000

Eth  场外指数613场外退场期第4天

爆破指数25

谢林点 3900

BNB 场外指数1004场外进场期第14天  逼近

爆破指数220

谢林点 750
"""

    def get_name(self) -> str:
        return "测试数据"
