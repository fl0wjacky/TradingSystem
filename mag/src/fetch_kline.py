#!/usr/bin/env python3
"""
抓取标的的真实日 K 线（OHLC），存入 mag_data.db 的 kline_data 表。

- 加密：Binance 现货日线（免 key）
- 美股/商品/亚股：Yahoo Finance（需未被限流的网络）

按 coin_daily_data 的日期范围**增量**抓取（每个标的从已有最新日期续拉），
幂等写入（INSERT OR REPLACE）；单个标的失败会被跳过并计入覆盖率报告，不中断整体。

两种用法：
  - CLI：  python3 src/fetch_kline.py [BTC ETH ...]
  - 页面：/chart 加载时调用 refresh_if_stale()，当天最多触发一次后台增量抓取
"""
import json
import sqlite3
import sys
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from src.kline_sources import get_source

DB_PATH = Path(__file__).parent.parent / 'mag_data.db'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36')

# 后台刷新的每日节流（内存标记 + 锁，保证一天只触发一次、且不并发重复抓取）
_refresh_lock = threading.Lock()
_refresh_marker = {'date': None}


def _http_get(url: str, timeout: int = 12) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def ensure_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS kline_data (
            date TEXT NOT NULL,
            coin TEXT NOT NULL,
            open REAL, high REAL, low REAL, close REAL,
            PRIMARY KEY (date, coin)
        )
    """)


def fetch_binance(symbol: str, start_date: str, base: str = 'https://api.binance.com/api/v3') -> list:
    """base 默认现货；传 fapi 基址即抓合约（代币化美股/商品/亚股）。两者 K 线格式一致。"""
    start_ms = int(datetime.strptime(start_date, '%Y-%m-%d')
                   .replace(tzinfo=timezone.utc).timestamp() * 1000)
    url = (f"{base}/klines?symbol={symbol}"
           f"&interval=1d&startTime={start_ms}&limit=1000")
    raw = json.loads(_http_get(url))
    now_ms = datetime.now(timezone.utc).timestamp() * 1000
    out = []
    for k in raw:
        if k[6] >= now_ms:   # 收盘时间(k[6])未到 = 当天K线还没走完，丢弃
            continue
        d = datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc).strftime('%Y-%m-%d')
        out.append((d, float(k[1]), float(k[2]), float(k[3]), float(k[4])))
    return out


def fetch_yahoo(ticker: str, start_date: str) -> list:
    p1 = int(datetime.strptime(start_date, '%Y-%m-%d')
             .replace(tzinfo=timezone.utc).timestamp())
    p2 = int(datetime.now(timezone.utc).timestamp()) + 86400
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
           f"?interval=1d&period1={p1}&period2={p2}")
    data = json.loads(_http_get(url))
    res = data['chart']['result'][0]
    ts = res['timestamp']
    q = res['indicators']['quote'][0]
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    out = []
    for i, t in enumerate(ts):
        o, h, l, c = q['open'][i], q['high'][i], q['low'][i], q['close'][i]
        if None in (o, h, l, c):
            continue
        d = datetime.fromtimestamp(t, tz=timezone.utc).strftime('%Y-%m-%d')
        if d >= today:   # 当天(未收盘)K线，丢弃
            continue
        out.append((d, float(o), float(h), float(l), float(c)))
    return out


def fetch_all(only=None, verbose=True) -> dict:
    """抓取所有（或指定）已映射标的的 K 线，增量续拉，幂等写入。返回覆盖率摘要。"""
    only = set(only) if only else None
    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)

    coins = [r[0] for r in conn.execute(
        "SELECT DISTINCT coin FROM coin_daily_data ORDER BY coin")]
    global_min = conn.execute("SELECT MIN(date) FROM coin_daily_data").fetchone()[0]
    # 每个标的已有的最新 K 线日期（用于增量）
    last_by_coin = dict(conn.execute(
        "SELECT coin, MAX(date) FROM kline_data GROUP BY coin").fetchall())

    ok, skipped, no_source = [], [], []
    for coin in coins:
        if only and coin not in only:
            continue
        src = get_source(coin)
        if not src:
            no_source.append(coin)
            continue
        source, symbol = src
        start = last_by_coin.get(coin) or global_min  # 增量起点
        try:
            if source == 'binance':
                bars = fetch_binance(symbol, start)
            elif source == 'binance_futures':
                bars = fetch_binance(symbol, start, base='https://fapi.binance.com/fapi/v1')
            else:
                bars = fetch_yahoo(symbol, start)
            if not bars:
                skipped.append(f"{coin}(空)")
                continue
            conn.executemany(
                "INSERT OR REPLACE INTO kline_data (date, coin, open, high, low, close) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(d, coin, o, h, l, c) for (d, o, h, l, c) in bars])
            conn.commit()
            ok.append(coin)
            if verbose:
                print(f"  ✓ {coin:12s} {source:8s} {symbol:14s} {len(bars)} 根 (自 {start})")
            time.sleep(0.2)
        except Exception as e:
            skipped.append(f"{coin}({type(e).__name__})")
            if verbose:
                print(f"  ✗ {coin:12s} {source:8s} {symbol:14s} 跳过: {e}")

    conn.close()
    summary = {'ok': ok, 'skipped': skipped, 'no_source': no_source}
    if verbose:
        print(f"\n成功 {len(ok)} · 跳过 {len(skipped)} · 无行情源 {len(no_source)}")
        if skipped:
            print("  跳过:", ", ".join(skipped))
        if no_source:
            print("  无源(仅场外/爆破):", ", ".join(no_source))
    return summary


def _latest_kline_date() -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        ensure_table(conn)
        row = conn.execute("SELECT MAX(date) FROM kline_data").fetchone()
        conn.close()
        return row[0]
    except Exception:
        return None


def refresh_if_stale() -> bool:
    """页面加载时调用：若 K 线不是最新，则当天触发一次后台增量抓取（不阻塞请求）。

    - 一天最多触发一次（内存标记），即使有并发访问或抓取失败也不会重复拉取同一天。
    - 已是最新（最新 K 线日期 >= 今天）则直接跳过。
    返回是否启动了后台刷新。
    """
    today = datetime.now().strftime('%Y-%m-%d')
    with _refresh_lock:
        if _refresh_marker['date'] == today:
            return False
        maxk = _latest_kline_date()
        if maxk and maxk >= today:
            _refresh_marker['date'] = today
            return False
        _refresh_marker['date'] = today  # 标记已尝试，避免失败时反复触发
    threading.Thread(target=lambda: fetch_all(verbose=False), daemon=True).start()
    return True


def main():
    if not DB_PATH.exists():
        print(f"错误：数据库不存在 - {DB_PATH}")
        sys.exit(1)
    fetch_all(only=sys.argv[1:] or None, verbose=True)


if __name__ == '__main__':
    main()
