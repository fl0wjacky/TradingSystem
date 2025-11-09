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
    """Firecrawl API 抓取器（使用官方 SDK）"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def scrape(self, url: str) -> Optional[str]:
        """使用 Firecrawl 官方 SDK 抓取数据"""
        try:
            from firecrawl import FirecrawlApp

            console.print(f"[dim]使用 {self.get_name()} 抓取数据...[/dim]")

            # 初始化 Firecrawl 客户端
            app = FirecrawlApp(api_key=self.api_key)

            # 调用 scrape 方法
            # maxAge: 使用2天内的缓存数据（可提速500%）
            # timeout: 120秒超时
            # waitFor: 等待5秒让 Notion 页面完全加载
            result = app.scrape(
                url,
                formats=['markdown'],
                max_age=172800000,  # 2天缓存 (默认值，毫秒)
                timeout=120000,     # 120秒 (毫秒)
                wait_for=5000,      # 等待5秒 (毫秒)
                only_main_content=True
            )

            # 检查返回结果
            if result and 'markdown' in result:
                console.print(f"[green]✓[/green] {self.get_name()} 抓取成功")
                return result['markdown']

            console.print(f"[yellow]✗ {self.get_name()} 抓取失败: 未返回 markdown 内容[/yellow]")
            return None

        except ImportError:
            console.print(f"[yellow]✗ {self.get_name()} 不可用: 缺少 firecrawl-py 库[/yellow]")
            console.print("[dim]安装: pip install firecrawl-py[/dim]")
            return None
        except Exception as e:
            console.print(f"[yellow]✗ {self.get_name()} 抓取失败: {e}[/yellow]")
            return None

    def get_name(self) -> str:
        return "Firecrawl SDK"


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


class PlaywrightScraper(BaseScraper):
    """使用 Playwright 的无头浏览器抓取器（支持 JavaScript 渲染）"""

    def scrape(self, url: str) -> Optional[str]:
        """使用 Playwright 无头浏览器抓取需要 JavaScript 渲染的页面"""
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

            console.print(f"[dim]使用 {self.get_name()} 抓取数据...[/dim]")

            with sync_playwright() as p:
                # 启动无头浏览器（适合服务器环境）
                browser = p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',              # 服务器环境必需
                        '--disable-dev-shm-usage',   # 避免共享内存问题
                        '--disable-gpu',             # 无 GPU 服务器
                        '--disable-software-rasterizer'
                    ]
                )

                page = browser.new_page()

                try:
                    # 访问页面，等待网络空闲（最多 120 秒）
                    page.goto(url, wait_until='networkidle', timeout=120000)

                    # 额外等待 5 秒，确保动态内容完全加载
                    page.wait_for_timeout(5000)

                    # 获取渲染后的纯文本内容
                    text = page.inner_text('body')

                    browser.close()

                    if text and len(text) > 100:  # 确保不是空页面
                        console.print(f"[green]✓[/green] {self.get_name()} 抓取成功")
                        return text

                    console.print(f"[yellow]✗ {self.get_name()} 抓取失败: 内容为空或过短[/yellow]")
                    return None

                except PlaywrightTimeout:
                    console.print(f"[yellow]✗ {self.get_name()} 抓取失败: 页面加载超时[/yellow]")
                    browser.close()
                    return None

        except ImportError:
            console.print(f"[yellow]✗ {self.get_name()} 不可用: 缺少 playwright 库[/yellow]")
            console.print("[dim]安装: pip install playwright && playwright install chromium --with-deps[/dim]")
            return None
        except Exception as e:
            console.print(f"[yellow]✗ {self.get_name()} 抓取失败: {e}[/yellow]")
            return None

    def get_name(self) -> str:
        return "Playwright 无头浏览器"


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
