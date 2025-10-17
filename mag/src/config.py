"""
配置管理模块
负责加载和管理系统配置，支持 .env 文件和命令行参数
"""
import os
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console()


class Config:
    """系统配置管理类"""

    def __init__(self):
        self.firecrawl_api_key: Optional[str] = None
        self.notion_api_token: Optional[str] = None
        self._loaded = False

    def load_from_env(self, env_path: Optional[str] = None):
        """
        从 .env 文件加载配置

        Args:
            env_path: .env 文件路径，默认为项目根目录的 .env
        """
        if env_path is None:
            # 获取项目根目录
            current_dir = Path(__file__).parent.parent
            env_path = current_dir / '.env'
        else:
            env_path = Path(env_path)

        if not env_path.exists():
            # 如果 .env 不存在，尝试创建
            self._create_env_file(env_path)
            return

        # 手动解析 .env 文件（不依赖 python-dotenv）
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过注释和空行
                    if not line or line.startswith('#'):
                        continue
                    # 解析 KEY=VALUE
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()

                        # 设置环境变量
                        if value:  # 只有非空值才设置
                            os.environ[key] = value

            # 读取配置
            self.firecrawl_api_key = os.getenv('FIRECRAWL_API_KEY')
            self.notion_api_token = os.getenv('NOTION_API_TOKEN')
            self._loaded = True

        except Exception as e:
            console.print(f"[yellow]警告: 读取配置文件失败: {e}[/yellow]")

    def _create_env_file(self, env_path: Path):
        """
        创建 .env 文件（从 .env.example 复制）

        Args:
            env_path: .env 文件路径
        """
        example_path = env_path.parent / '.env.example'

        if not example_path.exists():
            console.print("[yellow]警告: .env.example 文件不存在，无法自动创建配置[/yellow]")
            return

        try:
            # 复制 .env.example 到 .env
            import shutil
            shutil.copy(example_path, env_path)

            console.print(f"\n[green]✓[/green] 已自动创建配置文件: {env_path}")
            console.print("[yellow]请编辑 .env 文件，填入你的 API 密钥[/yellow]")
            console.print("[dim]提示: 至少配置一个 API 密钥以提高数据获取成功率[/dim]\n")

        except Exception as e:
            console.print(f"[red]错误: 创建配置文件失败: {e}[/red]")

    def override_from_args(self, firecrawl_key: Optional[str] = None,
                          notion_token: Optional[str] = None):
        """
        从命令行参数覆盖配置

        Args:
            firecrawl_key: Firecrawl API key
            notion_token: Notion API token
        """
        if firecrawl_key:
            self.firecrawl_api_key = firecrawl_key
            console.print("[dim]使用命令行提供的 Firecrawl API key[/dim]")

        if notion_token:
            self.notion_api_token = notion_token
            console.print("[dim]使用命令行提供的 Notion API token[/dim]")

    def has_firecrawl_api(self) -> bool:
        """是否配置了 Firecrawl API"""
        return bool(self.firecrawl_api_key)

    def has_notion_api(self) -> bool:
        """是否配置了 Notion API"""
        return bool(self.notion_api_token)

    def show_status(self):
        """显示配置状态"""
        console.print("\n[bold cyan]配置状态:[/bold cyan]")

        if self.has_firecrawl_api():
            console.print("  [green]✓[/green] Firecrawl API: 已配置")
        else:
            console.print("  [dim]✗ Firecrawl API: 未配置[/dim]")

        if self.has_notion_api():
            console.print("  [green]✓[/green] Notion API: 已配置")
        else:
            console.print("  [dim]✗ Notion API: 未配置[/dim]")

        console.print()


# 全局配置实例
config = Config()
