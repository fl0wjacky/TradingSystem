"""
配置管理模块
负责加载和管理系统配置，支持 .env 文件、YAML配置和命令行参数
"""
import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any
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


class MagConfig:
    """MAG系统修正参数配置类"""

    def __init__(self):
        # 数据库路径
        self.db_path = Path(__file__).parent.parent / 'mag_data.db'

        # 默认配置值
        self.benchmark_divergence = {
            'nasdaq': -10.0,
            'btc': -5.0,
            'dragon_leaders': {
                'ETH': -2.5,
                'BNB': -1.5,
                'SOL': -1.0,
                'DOGE': -0.5
            }
        }

        self.phase_transition = {
            'entry_phase': {'upward': 5.0, 'downward': -5.0},
            'exit_phase': {'upward': -5.0, 'downward': 5.0}
        }

        self.approaching_correction = -5.0

        self.break_index = {
            'entry_phase_day1_above_200': -2.5,
            'exit_phase_day1_below_0': -2.5
        }

        self.quality_thresholds = {
            'excellent_min': 5.0,
            'poor_max': -5.0
        }

        self.system = {
            'config_version': '1.0',
            'enable_validation': True
        }

        self._loaded = False

    def load_from_yaml(self, config_path: Optional[str] = None) -> bool:
        """
        从 YAML 配置文件加载

        Args:
            config_path: 配置文件路径，默认为项目根目录的 config.yaml

        Returns:
            bool: 加载是否成功
        """
        if config_path is None:
            # 获取项目根目录
            current_dir = Path(__file__).parent.parent
            config_path = current_dir / 'config.yaml'
            example_path = current_dir / 'config.example.yaml'
        else:
            config_path = Path(config_path)
            example_path = config_path.parent / 'config.example.yaml'

        # 如果 config.yaml 不存在，从 example 复制
        if not config_path.exists():
            if example_path.exists():
                console.print(f"[yellow]配置文件不存在，从示例文件创建: {config_path}[/yellow]")
                try:
                    import shutil
                    shutil.copy(example_path, config_path)
                    console.print(f"[green]✓[/green] 已创建配置文件: {config_path}")
                except Exception as e:
                    console.print(f"[red]错误: 创建配置文件失败: {e}[/red]")
                    console.print("[yellow]将使用默认配置[/yellow]")
                    return False
            else:
                console.print(f"[yellow]警告: 配置文件不存在: {config_path}[/yellow]")
                console.print("[yellow]将使用默认配置[/yellow]")
                return False

        # 加载配置文件
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)

            if not config_data:
                console.print("[yellow]警告: 配置文件为空，使用默认配置[/yellow]")
                return False

            # 加载各项配置（如果存在则覆盖默认值）
            if 'benchmark_divergence' in config_data:
                self._merge_dict(self.benchmark_divergence, config_data['benchmark_divergence'])

            if 'phase_transition' in config_data:
                self._merge_dict(self.phase_transition, config_data['phase_transition'])

            if 'approaching_correction' in config_data:
                self.approaching_correction = float(config_data['approaching_correction'])

            if 'break_index' in config_data:
                self._merge_dict(self.break_index, config_data['break_index'])

            if 'quality_thresholds' in config_data:
                self._merge_dict(self.quality_thresholds, config_data['quality_thresholds'])

            if 'system' in config_data:
                self._merge_dict(self.system, config_data['system'])

            self._loaded = True

            # 验证配置
            if self.system.get('enable_validation', True):
                self._validate_config()

            console.print(f"[green]✓[/green] 成功加载配置文件: {config_path}")
            return True

        except yaml.YAMLError as e:
            console.print(f"[red]错误: YAML 解析失败: {e}[/red]")
            console.print("[yellow]将使用默认配置[/yellow]")
            return False
        except Exception as e:
            console.print(f"[red]错误: 加载配置文件失败: {e}[/red]")
            console.print("[yellow]将使用默认配置[/yellow]")
            return False

    def _merge_dict(self, target: Dict, source: Dict):
        """递归合并字典"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._merge_dict(target[key], value)
            else:
                target[key] = value

    def _validate_config(self):
        """验证配置有效性"""
        errors = []

        # 验证对标链背离修正
        if self.benchmark_divergence['nasdaq'] > 0:
            errors.append("benchmark_divergence.nasdaq 应该是负值")
        if self.benchmark_divergence['btc'] > 0:
            errors.append("benchmark_divergence.btc 应该是负值")

        # 验证质量阈值
        if self.quality_thresholds['excellent_min'] <= self.quality_thresholds['poor_max']:
            errors.append("quality_thresholds.excellent_min 应该大于 poor_max")

        if errors:
            console.print("[yellow]配置验证警告:[/yellow]")
            for error in errors:
                console.print(f"  [yellow]⚠[/yellow] {error}")

    def show_config(self):
        """显示当前配置"""
        console.print("\n[bold cyan]当前MAG配置:[/bold cyan]")

        console.print("\n[bold]对标链背离修正:[/bold]")
        console.print(f"  纳指: {self.benchmark_divergence['nasdaq']:+.1f}%")
        console.print(f"  BTC: {self.benchmark_divergence['btc']:+.1f}%")
        console.print("  龙头币:")
        for coin, weight in self.benchmark_divergence['dragon_leaders'].items():
            console.print(f"    {coin}: {weight:+.1f}%")

        console.print("\n[bold]相变修正:[/bold]")
        console.print(f"  进场期向上: {self.phase_transition['entry_phase']['upward']:+.1f}%")
        console.print(f"  进场期向下: {self.phase_transition['entry_phase']['downward']:+.1f}%")
        console.print(f"  退场期向上: {self.phase_transition['exit_phase']['upward']:+.1f}%")
        console.print(f"  退场期向下: {self.phase_transition['exit_phase']['downward']:+.1f}%")

        console.print(f"\n[bold]逼近修正:[/bold] {self.approaching_correction:+.1f}%")

        console.print("\n[bold]爆破指数修正:[/bold]")
        console.print(f"  进场期第1天爆破>200: {self.break_index['entry_phase_day1_above_200']:+.1f}%")
        console.print(f"  退场期第1天爆破<0: {self.break_index['exit_phase_day1_below_0']:+.1f}%")

        console.print("\n[bold]质量评级阈值:[/bold]")
        console.print(f"  优质门槛: > {self.quality_thresholds['excellent_min']:+.1f}%")
        console.print(f"  劣质门槛: < {self.quality_thresholds['poor_max']:+.1f}%")

        console.print()


# 全局配置实例
config = Config()
mag_config = MagConfig()
