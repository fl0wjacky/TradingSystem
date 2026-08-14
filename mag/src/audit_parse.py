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

# 含「场外指数<数字>」或「场外指<数字>」(缺数)的行 = 一个预期数据条目
EXPECT_RE = re.compile(r'场外指数?\s*-?\d')
# 从数据行里取一个用于展示的数值，判断是否已被解析
OFFCHAIN_RE = re.compile(r'场外指数?\s*(\d+)')
DATE_RE = re.compile(r'^(?:\d{4}\.)?\d{1,2}\.\d{1,2}$')


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
        expect_lines = [l for l in lines if EXPECT_RE.search(l)]
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
                m = OFFCHAIN_RE.search(l)
                val = int(m.group(1)) if m else None
                if val is None or val not in parsed_vals:
                    missed.append(l)
            if missed:
                ts = memo.find('div', class_='time')
                gap_notes.append((ts.get_text(strip=True) if ts else '?', drow, missed))

    print(f"巡检文件：{html_path.name}")
    print(f"笔记数 {total_notes} · 预期数据条目 {total_expect} · 解析入库 {total_parsed} "
          f"· 覆盖率 {total_parsed / total_expect * 100:.1f}%")
    n_missed_lines = sum(len(m) for _, _, m in gap_notes)
    print(f"疑似漏解析：{len(gap_notes)} 条笔记 / {n_missed_lines} 行\n")

    if gap_notes:
        print("明细（时间 · 日期行 · 未解析的数据行）：")
        for ts, drow, missed in gap_notes:
            for l in missed:
                print(f"  [{ts} · {drow}] {l}")
    else:
        print("✓ 无漏解析")


if __name__ == '__main__':
    main()
