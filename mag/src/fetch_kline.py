#!/usr/bin/env python3
"""
抓取标的的真实日 K 线（OHLC），存入 mag_data.db 的 kline_data 表。

- 加密：Binance 现货日线（免 key）
- 美股/商品/亚股：Yahoo Finance（需未被限流的网络）

按 coin_daily_data 的日期范围抓取，幂等写入（INSERT OR REPLACE）；
单个标的抓取失败（下架/限流/网络）会被跳过并计入覆盖率报告，不中断整体。

用法:
  python3 src/fetch_kline.py            # 抓取全部已映射标的
  python3 src/fetch_kline.py BTC ETH    # 只抓指定标的
"""
import json
import sqlite3
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from src.kline_sources import get_source

DB_PATH = Path(__file__).parent.parent / 'mag_data.db'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36')


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


def fetch_binance(symbol: str, start_date: str) -> list:
    """返回 [(date, o, h, l, c), ...]"""
    start_ms = int(datetime.strptime(start_date, '%Y-%m-%d')
                   .replace(tzinfo=timezone.utc).timestamp() * 1000)
    url = (f"https://api.binance.com/api/v3/klines?symbol={symbol}"
           f"&interval=1d&startTime={start_ms}&limit=1000")
    raw = json.loads(_http_get(url))
    out = []
    for k in raw:
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
    out = []
    for i, t in enumerate(ts):
        o, h, l, c = q['open'][i], q['high'][i], q['low'][i], q['close'][i]
        if None in (o, h, l, c):
            continue
        d = datetime.fromtimestamp(t, tz=timezone.utc).strftime('%Y-%m-%d')
        out.append((d, float(o), float(h), float(l), float(c)))
    return out


def main():
    if not DB_PATH.exists():
        print(f"错误：数据库不存在 - {DB_PATH}")
        sys.exit(1)

    only = set(sys.argv[1:])  # 指定标的（可选）

    conn = sqlite3.connect(DB_PATH)
    ensure_table(conn)

    # 数据库里的标的与整体起始日期
    coins = [r[0] for r in conn.execute(
        "SELECT DISTINCT coin FROM coin_daily_data ORDER BY coin")]
    start_date = conn.execute("SELECT MIN(date) FROM coin_daily_data").fetchone()[0]

    ok, skipped, no_source = [], [], []
    for coin in coins:
        if only and coin not in only:
            continue
        src = get_source(coin)
        if not src:
            no_source.append(coin)
            continue
        source, symbol = src
        try:
            if source == 'binance':
                bars = fetch_binance(symbol, start_date)
            else:
                bars = fetch_yahoo(symbol, start_date)
            if not bars:
                skipped.append(f"{coin}(空)")
                continue
            conn.executemany(
                "INSERT OR REPLACE INTO kline_data (date, coin, open, high, low, close) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                [(d, coin, o, h, l, c) for (d, o, h, l, c) in bars])
            conn.commit()
            ok.append(f"{coin}({source}:{len(bars)})")
            print(f"  ✓ {coin:12s} {source:8s} {symbol:14s} {len(bars)} 根")
            time.sleep(0.25)  # 温和限速
        except (urllib.error.HTTPError, urllib.error.URLError, Exception) as e:
            skipped.append(f"{coin}({type(e).__name__})")
            print(f"  ✗ {coin:12s} {source:8s} {symbol:14s} 跳过: {e}")

    conn.close()
    print(f"\n成功 {len(ok)} · 跳过 {len(skipped)} · 无行情源 {len(no_source)}")
    if skipped:
        print("  跳过:", ", ".join(skipped))
    if no_source:
        print("  无源(仅场外/爆破):", ", ".join(no_source))


if __name__ == '__main__':
    main()
