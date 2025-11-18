"""
Notion数据抓取与解析模块
实现多种抓取方式的降级策略
"""
import re
from typing import List, Dict, Optional
from datetime import datetime
from rich.console import Console

# 导入抓取器和配置
from src.scrapers import (
    BaseScraper,
    FirecrawlAPIScraper,
    NotionAPIScraper,
    PlaywrightScraper
)
from src.config import config

console = Console()


class NotionScraper:
    def __init__(self, url: str):
        self.url = url
        self.dragon_leaders = ['ETH', 'BNB', 'SOL', 'DOGE']  # 默认龙头币列表

    def fetch_data(self) -> str:
        """
        从Notion抓取原始文本数据
        使用降级策略，按优先级尝试多种方式
        """
        console.print("\n[bold cyan]开始抓取 Notion 数据...[/bold cyan]")
        console.print(f"[dim]URL: {self.url}[/dim]\n")

        # 构建抓取器列表（按优先级排序）
        scrapers: List[BaseScraper] = []

        # 优先级1: Firecrawl SDK（云端渲染，有缓存，最快）
        if config.has_firecrawl_api():
            scrapers.append(FirecrawlAPIScraper(config.firecrawl_api_key))

        # 优先级2: Playwright 无头浏览器（本地渲染，支持 JS）
        scrapers.append(PlaywrightScraper())

        # 优先级3: Notion API（如果配置了 token）
        if config.has_notion_api():
            scrapers.append(NotionAPIScraper(config.notion_api_token))

        # 显示降级策略
        console.print("[dim]降级策略顺序:[/dim]")
        for i, scraper in enumerate(scrapers, start=1):
            console.print(f"[dim]  {i}. {scraper.get_name()}[/dim]")
        console.print()

        # 按顺序尝试各个抓取器
        for scraper in scrapers:
            raw_text = scraper.scrape(self.url)
            if raw_text:
                return raw_text

        # 如果所有方法都失败
        raise Exception(
            "所有抓取方式均失败。\n"
            "请检查：\n"
            "1. 网络连接是否正常\n"
            "2. Notion 页面是否可访问（可能需要等待页面加载完成）\n"
            "3. Firecrawl API 配置是否正确（推荐）\n"
            "4. Playwright 是否正常安装（playwright install chromium --with-deps）\n"
            "5. Notion API Token 是否有效（可选）"
        )

    def parse_data(self, raw_text: str) -> List[Dict]:
        """解析Notion页面文本，提取币种数据 - 使用灵活的状态机"""
        data_list = []

        # 提取日期 - 支持带年份和不带年份两种格式
        # 格式1: 2024.11.16 (带年份)
        # 格式2: 11.16 (不带年份，使用当前年份)
        date_match_with_year = re.search(r'(\d{4})\.(\d{1,2})\.(\d{1,2})', raw_text)
        if date_match_with_year:
            year = date_match_with_year.group(1)
            month = date_match_with_year.group(2)
            day = date_match_with_year.group(3)
            formatted_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        else:
            date_match = re.search(r'(\d{1,2}\.\d{1,2})', raw_text)
            if not date_match:
                raise Exception("未找到日期信息")
            date_str = date_match.group(1)
            month, day = date_str.split('.')
            current_year = datetime.now().year
            formatted_date = f"{current_year}-{month.zfill(2)}-{day.zfill(2)}"

        lines = raw_text.split('\n')

        # 状态机解析
        i = 0
        in_us_stock_section = False  # 是否在美股区

        while i < len(lines):
            line = lines[i].strip()
            i += 1

            # 检测美股区标志
            if '大宗$美股区' in line or '大宗美股区' in line:
                in_us_stock_section = True
                continue

            # 检测其他区域标志，退出美股区
            if (line.startswith('大宗') or line.startswith('※')) and '美股' not in line:
                in_us_stock_section = False

            # 跳过空行和分隔符
            if not line or line.startswith('※') or line.startswith('♤') or line.startswith('$$$') or line.startswith('&'):
                continue

            # 尝试提取币种信息 - 多种格式兼容
            coin_data = self._try_parse_coin_block(lines, i - 1, formatted_date, in_us_stock_section)
            if coin_data:
                data_list.append(coin_data)

        if not data_list:
            raise Exception("未能解析出任何币种数据")

        return data_list

    def _try_parse_coin_block(self, lines: List[str], start_idx: int, date: str, in_us_stock_section: bool = False) -> Optional[Dict]:
        """
        尝试从指定行开始解析一个币种数据块
        支持多种格式变体
        """
        if start_idx >= len(lines):
            return None

        line = lines[start_idx].strip()

        # === 黑名单检查：排除已知的非币种词 ===
        # 这些是参考数据、标题等，不应被解析为币种
        non_coin_patterns = [
            r'^前值$',  # 前值参考数据
            r'^[进退]场期第\d+[天月]$',  # 独立的"进场期第X天"等描述行
            r'.*更新.*',  # 包含"更新"
            r'.*详述.*',  # 包含"详述"
            r'.*更在.*',  # 包含"更在"
        ]
        for pattern in non_coin_patterns:
            if re.match(pattern, line):
                return None

        # === 格式1: 标准格式 ===
        # Btc  场外指数682场外退场期第4天
        # Doge场外指数486场外退场期第4天（无空格）
        # 美股纳指 OTC 场外指数847场外退场期第4天（包含中文和空格）
        # btc 场外指数1164 场外进场期第1天（场外指数和进场期之间有空格）
        # Ondo 场外指数526场外退场第36天（无"期"字）
        match1 = re.match(r'^([A-Za-z\u4e00-\u9fa5$]+(?:\s+[A-Z]+)?(?:（[^）]+）)?)\s*场外指数(\d+)\s*(?:场外)?(进场|退场)期?第?(\d+)(天|月)', line)
        if match1:
            # 统一格式：补充"期"字
            phase_type = match1.group(3) + '期'
            return self._extract_coin_data(
                coin_name=match1.group(1),
                offchain_index=int(match1.group(2)),
                phase_type=phase_type,
                phase_days=int(match1.group(4)),
                lines=lines,
                start_idx=start_idx,
                date=date,
                in_us_stock_section=in_us_stock_section
            )

        # === 格式2: 紧凑格式（爆破指数在同一行）===
        # hood 场外指数1089爆破114
        # 布伦特原油 场外指数798爆破指数-25
        # circle 场外指数1125 爆破指数261（场外指数和爆破之间有空格）
        match2 = re.match(r'^([A-Za-z\u4e00-\u9fa5]+)\s+场外指数(\d+)\s*爆破(?:指数)?(-?\d+)', line)
        if match2:
            # 向下查找进退场期信息
            phase_info = self._find_phase_info(lines, start_idx + 1)
            if phase_info:
                return self._build_coin_data(
                    coin_name=match2.group(1),
                    offchain_index=int(match2.group(2)),
                    break_index=int(match2.group(3)),
                    phase_type=phase_info['phase_type'],
                    phase_days=phase_info['phase_days'],
                    shelin_point=self._find_shelin(lines, start_idx),
                    is_approaching=self._find_approaching(lines, start_idx),
                    date=date,
                    in_us_stock_section=in_us_stock_section
                )

        # === 格式3: 币名单独一行 ===
        # $Trump
        # 场外指数357爆破指数-14
        # 场外退场第6天
        # 地产 （指导国内购置地产房产 大周期只月更）
        # 场外指数1764 爆破238
        # 进场期第3月
        is_chinese_coin = re.match(r'^[\u4e00-\u9fa5]+(?:\s+（[^）]+）)?$', line)
        is_english_coin = re.match(r'^[\$]?[A-Za-z]+$', line)

        if is_english_coin or is_chinese_coin:
            # 中文币种需要额外验证：检查下一行是否是币种名（排除分节标题和说明文字）
            if is_chinese_coin:
                # 查找下一个非空行
                next_non_empty = None
                for k in range(start_idx + 1, min(start_idx + 3, len(lines))):
                    if lines[k].strip():
                        next_non_empty = lines[k].strip()
                        break

                # 如果下一行是英文币种名，说明当前行是分节标题，跳过
                if next_non_empty and re.match(r'^[\$]?[A-Za-z]+', next_non_empty):
                    return None  # 跳过此行

                # 如果下一行也是纯中文，说明当前行是说明文字，跳过
                # 这避免了"数据拟合平滑还需要时间"+"台积电"这种情况
                if next_non_empty and re.match(r'^[\u4e00-\u9fa5]+(?:\s+（[^）]+）)?$', next_non_empty):
                    return None  # 跳过此行

            # 向下查找完整信息
            for j in range(start_idx + 1, min(start_idx + 5, len(lines))):
                next_line = lines[j].strip()
                if not next_line:
                    continue

                # 查找：场外指数XXX爆破指数XXX 或 场外指数XXX 爆破XXX（地产格式）
                combined = re.match(r'场外指数(\d+)\s*爆破(?:指数)?\s*(-?\d+)', next_line)
                if combined:
                    # 从币名开始向下查找进退场期(覆盖进退场期在场外指数前后的情况)
                    phase_info = self._find_phase_info(lines, start_idx + 1)
                    if phase_info:
                        return self._build_coin_data(
                            coin_name=line.strip('$'),
                            offchain_index=int(combined.group(1)),
                            break_index=int(combined.group(2)),
                            phase_type=phase_info['phase_type'],
                            phase_days=phase_info['phase_days'],
                            shelin_point=self._find_shelin(lines, start_idx),
                            is_approaching=self._find_approaching(lines, start_idx),
                            date=date,
                            in_us_stock_section=in_us_stock_section
                        )

                # 查找：场外指数XXX 单独，爆破指数在下一行
                only_off = re.match(r'场外指数(\d+)$', next_line)
                if only_off:
                    break_info = self._find_break_index(lines, j + 1)
                    # 从币名开始向下查找进退场期(覆盖进退场期在场外指数前后的情况)
                    phase_info = self._find_phase_info(lines, start_idx + 1)
                    if break_info is not None and phase_info:
                        return self._build_coin_data(
                            coin_name=line.strip('$'),
                            offchain_index=int(only_off.group(1)),
                            break_index=break_info,
                            phase_type=phase_info['phase_type'],
                            phase_days=phase_info['phase_days'],
                            shelin_point=self._find_shelin(lines, start_idx),
                            is_approaching=self._find_approaching(lines, start_idx),
                            date=date,
                            in_us_stock_section=in_us_stock_section
                        )

        # === 格式4: 特殊格式（地产等）===
        # 地产 场外指数1764 爆破238 进场期第3月
        match4 = re.match(r'^([^ ]+)\s+(?:（[^）]+）\s+)?场外指数(\d+)\s+爆破(?:指数)?(\d+)', line)
        if match4:
            # 验证币种名不是"进/退场期第X天"格式
            coin_name_candidate = match4.group(1)
            if re.match(r'^[进退]场期?第\d+[天月]', coin_name_candidate):
                return None  # 跳过"进场期第61天 场外指数2618 爆破指数323"这类行

            phase_info = self._find_phase_info(lines, start_idx)
            if phase_info:
                return self._build_coin_data(
                    coin_name=match4.group(1),
                    offchain_index=int(match4.group(2)),
                    break_index=int(match4.group(3)),
                    phase_type=phase_info['phase_type'],
                    phase_days=phase_info['phase_days'],
                    shelin_point=None,
                    is_approaching=self._find_approaching(lines, start_idx),
                    date=date,
                    in_us_stock_section=in_us_stock_section
                )

        return None

    def _extract_coin_data(self, coin_name: str, offchain_index: int, phase_type: str,
                          phase_days: int, lines: List[str], start_idx: int, date: str,
                          in_us_stock_section: bool = False) -> Dict:
        """从标准格式中提取完整币种数据"""
        break_index = self._find_break_index(lines, start_idx + 1)
        shelin_point = self._find_shelin(lines, start_idx)
        is_approaching = self._find_approaching(lines, start_idx)

        return self._build_coin_data(
            coin_name=coin_name,
            offchain_index=offchain_index,
            break_index=break_index,
            phase_type=phase_type,
            phase_days=phase_days,
            shelin_point=shelin_point,
            is_approaching=is_approaching,
            date=date,
            in_us_stock_section=in_us_stock_section
        )

    def _find_break_index(self, lines: List[str], start_idx: int) -> Optional[int]:
        """向下查找爆破指数"""
        for j in range(start_idx, min(start_idx + 10, len(lines))):
            search_line = lines[j].strip()
            if not search_line:
                continue
            match = re.search(r'爆破(?:指数\s*)?(-?\d+)', search_line)
            if match:
                return int(match.group(1))
            # 如果遇到下一个币种，停止
            if re.match(r'^[A-Za-z$]+\s+场外指数', search_line):
                break
        return None

    def _find_shelin(self, lines: List[str], start_idx: int) -> Optional[float]:
        """向下查找谢林点"""
        # 从 start_idx+1 开始搜索，跳过币种名称行本身，避免误判为"遇到下一个币种"
        for j in range(start_idx + 1, min(start_idx + 10, len(lines))):
            search_line = lines[j].strip()
            if not search_line:
                continue
            match = re.search(r'谢林点\s*([\d.]+)', search_line)
            if match:
                return float(match.group(1))
            # 如果遇到下一个币种，停止
            if re.match(r'^[A-Za-z$]+\s+场外指数', search_line):
                break
        return None

    def _find_approaching(self, lines: List[str], start_idx: int) -> int:
        """
        向下查找逼近关键字
        使用双重边界识别：
        1. 币名行识别（英文/中文单独行）
        2. 数据关键词第2次出现（场外指数/爆破指数）
        """
        seen_data_keyword = False  # 追踪是否已见过数据关键词

        for j in range(start_idx, min(start_idx + 10, len(lines))):
            if j >= len(lines):
                break
            search_line = lines[j].strip()
            if not search_line:
                continue

            # 追踪数据关键词（场外指数/爆破指数）
            if '场外指数' in search_line or '爆破指数' in search_line:
                if seen_data_keyword:
                    # 第2次遇到数据关键词 → 新币种的数据区，停止
                    break
                seen_data_keyword = True

            # 停止条件：只在start_idx之后检查（跳过币名行本身）
            if j > start_idx:
                # 停止条件A1：英文币名（含$符号）
                if re.match(r'^[\$]?[A-Za-z]+$', search_line):
                    break
                # 停止条件A2：中文币名（1-4个纯中文字符）
                if re.match(r'^[\u4e00-\u9fa5]{1,4}$', search_line):
                    break

            # 检查是否包含"逼近"
            if '逼近' in search_line:
                return 1
        return 0

    def _find_phase_info(self, lines: List[str], start_idx: int) -> Optional[Dict]:
        """向下查找进退场期信息"""
        for j in range(start_idx, min(start_idx + 5, len(lines))):
            search_line = lines[j].strip()
            if not search_line:
                continue
            # 支持两种格式：场外进场期第X天 和 场外进场第X天
            match = re.search(r'(?:场外)?(进场|退场)期?第?(\d+)(天|月)', search_line)
            if match:
                # 统一格式：补充"期"字
                phase_type = match.group(1) + '期'
                return {
                    'phase_type': phase_type,
                    'phase_days': int(match.group(2))
                }
            # 如果遇到下一个币种，停止
            if re.match(r'^[A-Za-z$]+(?:\s+场外指数|\s*$)', search_line):
                break
        return None

    def _build_coin_data(self, coin_name: str, offchain_index: int, break_index: Optional[int],
                        phase_type: str, phase_days: int, shelin_point: Optional[float],
                        is_approaching: int, date: str, in_us_stock_section: bool = False) -> Optional[Dict]:
        """构建币种数据字典"""
        if break_index is None:
            return None

        # 清理币名
        coin_name = coin_name.upper().strip('$')
        # 移除中文括号内容
        coin_name = re.sub(r'（[^）]+）', '', coin_name).strip()

        # 特殊处理：美股
        is_us_stock = 0
        us_stock_list = ['纳指', 'NASDAQ', 'COIN', 'AAPL', 'HOOD', 'TSLA', 'NVDA', 'MSTR']

        # 方式1: 如果在美股区，直接标记为美股
        if in_us_stock_section:
            is_us_stock = 1
        # 方式2: 检查是否是特定的美股名称（完全匹配）
        else:
            for us_stock in us_stock_list:
                # 使用完全匹配，避免 AAPL 匹配到 AAVE
                if coin_name == us_stock.upper():
                    is_us_stock = 1
                    break
                # 特殊处理含中文的纳指
                if us_stock in ['纳指', 'NASDAQ'] and (us_stock in coin_name or 'NASDAQ' in coin_name):
                    coin_name = 'NASDAQ'
                    is_us_stock = 1
                    break

        # 特殊处理：黄金
        if '黄金' in coin_name or 'GOLD' in coin_name.upper():
            coin_name = 'GOLD'

        # 特殊处理：原油
        if '原油' in coin_name or 'OIL' in coin_name.upper() or '布伦特' in coin_name:
            coin_name = 'OIL'

        # 判断是否为龙头币
        is_dragon_leader = 1 if coin_name in self.dragon_leaders else 0

        return {
            'date': date,
            'coin': coin_name,
            'phase_type': phase_type,
            'phase_days': phase_days,
            'offchain_index': offchain_index,
            'break_index': break_index,
            'shelin_point': shelin_point,
            'is_dragon_leader': is_dragon_leader,
            'is_us_stock': is_us_stock,
            'is_approaching': is_approaching
        }

    def scrape_and_parse(self) -> List[Dict]:
        """完整流程：抓取并解析数据"""
        raw_text = self.fetch_data()
        return self.parse_data(raw_text)


def scrape_notion_url(url: str) -> List[Dict]:
    """便捷函数：从URL抓取并解析数据"""
    scraper = NotionScraper(url)
    return scraper.scrape_and_parse()
