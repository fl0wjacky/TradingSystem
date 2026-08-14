#!/usr/bin/env python3
"""
解析巡检：比对浮墨笔记里的「预期数据条目」与「实际解析出的标的」，
一次性揪出所有漏解析的行（如缺"数"、括号异常、爆破挤同行、数值笔误等）。

原理：每条 #Mag 笔记里，每个含「场外指数<数字>」的行大致对应一个标的数据条目。
用与导入完全相同的解析器解析该笔记，若「预期条目数 > 解析出的标的数」，
则该笔记有漏解析，逐行列出未被解析的疑似数据行供人工核对。

用法：
  python3 src/audit_parse.py [flow的笔记.html]
"""
import re
import sys
from pathlib import Path

from bs4 import BeautifulSoup
from src.notion_scraper import NotionScraper

DEFAULT_HTML = Path(__file__).parent.parent / 'flow的笔记.html'

# 从数据行里取一个用于展示的数值，判断是否已被解析
OFFCHAIN_RE = re.compile(r'场外指数?\s*(\d+)')
DATE_RE = re.compile(r'^(?:\d{4}\.)?\d{1,2}\.\d{1,2}$')
# 正文/策略/区域标题里也常出现「场外指数」，需排除，避免误报
_PROSE_RE = re.compile(r'流动性|止盈|分批|期间|概况|提醒|复盘|问答|策略|建仓|对冲|下降|上涨|突破')


def is_data_line(l: str) -> bool:
    """判断一行是否为「标的数据条目」（名字 … 场外指数<数字> …），排除正文/标题。"""
    if not l or l[0] in '&※♤$$$':
        return False
    if l.startswith('场外'):          # 以"场外指数"开头 = 孤立续行/正文，非条目
        return False
    m = re.search(r'场外指数?\s*\d', l)
    if not m:
        return False
    prefix = l[:m.start()].strip()    # 场外指数前必须有个不太长的币名
    if not prefix or len(prefix) > 12:
        return False
    if _PROSE_RE.search(l):
        return False
    return True


def memo_lines(memo):
    c = memo.find('div', class_='content')
    if not c:
        return None
    lines = []
    for p in c.find_all('p'):
        for br in p.find_all('br'):
            br.replace_with('\n')
        for l in p.get_text(strip=False).split('\n'):
            if l.strip():
                lines.append(l.strip())
    return lines


def main():
    html_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_HTML
    if not html_path.exists():
        print(f"错误：文件不存在 - {html_path}")
        sys.exit(1)

    soup = BeautifulSoup(html_path.read_text(encoding='utf-8'), 'html.parser')
    scraper = NotionScraper("")

    total_notes = 0
    total_expect = 0
    total_parsed = 0
    gap_notes = []  # (时间戳, 日期行, [未解析的行])

    for memo in soup.find_all('div', class_='memo'):
        lines = memo_lines(memo)
        if not lines or '#Mag' not in lines[0]:
            continue
        drow = next((l for l in lines[1:5] if DATE_RE.match(l)), None)
        if not drow:
            continue  # 无日期行的笔记导入时本就跳过
        total_notes += 1

        # 预期数据行
        expect_lines = [l for l in lines if is_data_line(l)]
        total_expect += len(expect_lines)

        # 实际解析
        try:
            parsed = scraper.parse_data('\n'.join(lines))
        except Exception:
            parsed = []
        total_parsed += len(parsed)

        if len(expect_lines) > len(parsed):
            # 已解析出的场外指数值集合，用于标出哪些数据行没被解析
            parsed_vals = {p['offchain_index'] for p in parsed}
            missed = []
            for l in expect_lines:
                # 跳过忽略名单里的标的（如"美股 OTC"，本就不导入）
                if any(l.startswith(name) for name in scraper.ignore_names):
                    continue
                m = OFFCHAIN_RE.search(l)
                val = int(m.group(1)) if m else None
                if val is None or val not in parsed_vals:
                    missed.append(l)
            if missed:
                ts = memo.find('div', class_='time')
                gap_notes.append((ts.get_text(strip=True) if ts else '?', drow, missed))

    n_missed_lines = sum(len(m) for _, _, m in gap_notes)
    print(f"巡检文件：{html_path.name}")
    print(f"#Mag 笔记 {total_notes} 条 · 已解析标的记录 {total_parsed} 条")
    print(f"疑似漏解析：{len(gap_notes)} 条笔记 / {n_missed_lines} 行（下方逐行列出，供人工核对）\n")

    if gap_notes:
        print("明细（时间 · 日期行 · 未解析的数据行）：")
        for ts, drow, missed in gap_notes:
            for l in missed:
                print(f"  [{ts} · {drow}] {l}")
    else:
        print("✓ 无漏解析")


if __name__ == '__main__':
    main()
