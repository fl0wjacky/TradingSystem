"""
Notion数据抓取与解析模块
"""
import re
from typing import List, Dict, Optional
from datetime import datetime


class NotionScraper:
    def __init__(self, url: str):
        self.url = url
        self.dragon_leaders = ['ETH', 'BNB', 'SOL', 'DOGE']  # 默认龙头币列表

    def fetch_data(self) -> str:
        """
        从Notion抓取原始文本数据
        由于Notion需要JavaScript渲染，这里返回提示信息
        实际使用时请用Firecrawl或其他方式获取渲染后的文本
        """
        raise Exception(
            "Notion页面需要JavaScript渲染。\n"
            "请使用以下方式之一：\n"
            "1. 使用Firecrawl MCP工具抓取（推荐）\n"
            "2. 手动复制页面文本并保存为文件，然后使用parse_data()方法解析"
        )

    def parse_data(self, raw_text: str) -> List[Dict]:
        """解析Notion页面文本，提取币种数据 - 使用灵活的状态机"""
        data_list = []

        # 提取日期
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

        # === 格式1: 标准格式 ===
        # Btc  场外指数682场外退场期第4天
        # Doge场外指数486场外退场期第4天（无空格）
        # 美股纳指 OTC 场外指数847场外退场期第4天（包含中文和空格）
        match1 = re.match(r'^([A-Za-z\u4e00-\u9fa5$]+(?:\s+[A-Z]+)?(?:（[^）]+）)?)\s*场外指数(\d+)(?:场外)?(进场期|退场期)第?(\d+)(天|月)', line)
        if match1:
            return self._extract_coin_data(
                coin_name=match1.group(1),
                offchain_index=int(match1.group(2)),
                phase_type=match1.group(3),
                phase_days=int(match1.group(4)),
                lines=lines,
                start_idx=start_idx,
                date=date,
                in_us_stock_section=in_us_stock_section
            )

        # === 格式2: 紧凑格式（爆破指数在同一行）===
        # hood 场外指数1089爆破114
        # 布伦特原油 场外指数798爆破指数-25
        match2 = re.match(r'^([A-Za-z\u4e00-\u9fa5]+)\s+场外指数(\d+)爆破(?:指数)?(-?\d+)', line)
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
        if re.match(r'^[\$]?[A-Za-z]+$', line):
            # 向下查找完整信息
            for j in range(start_idx + 1, min(start_idx + 5, len(lines))):
                next_line = lines[j].strip()
                if not next_line:
                    continue

                # 查找：场外指数XXX爆破指数XXX
                combined = re.match(r'场外指数(\d+)爆破指数(-?\d+)', next_line)
                if combined:
                    phase_info = self._find_phase_info(lines, j + 1)
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
                    phase_info = self._find_phase_info(lines, j + 1)
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
        for j in range(start_idx, min(start_idx + 10, len(lines))):
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
        """向下查找逼近关键字"""
        for j in range(start_idx, min(start_idx + 10, len(lines))):
            if j >= len(lines):
                break
            search_line = lines[j].strip()
            if not search_line:
                continue
            # 检查是否包含"逼近"
            if '逼近' in search_line:
                return 1
            # 如果遇到下一个币种，停止（更宽松的匹配）
            # 只有当行首是币种名且后面跟着"场外"或单独的币名时才停止
            if j > start_idx:  # 跳过当前行本身
                if re.match(r'^[A-Za-z$]+(?:\s+场外|\s*$)', search_line):
                    break
        return 0

    def _find_phase_info(self, lines: List[str], start_idx: int) -> Optional[Dict]:
        """向下查找进退场期信息"""
        for j in range(start_idx, min(start_idx + 5, len(lines))):
            search_line = lines[j].strip()
            if not search_line:
                continue
            match = re.search(r'(?:场外)?(进场期|退场期)第?(\d+)(天|月)', search_line)
            if match:
                return {
                    'phase_type': match.group(1),
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
        coin_name = re.sub(r'（[^）]+）', '', coin_name)

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
