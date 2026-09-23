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
from datetime import datetime, timezone, timedelta
from pathlib import Path

from src.kline_sources import get_source

DB_PATH = Path(__file__).parent.parent / 'mag_data.db'
UA = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
      'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36')

# 后台刷新的节流（内存标记 + 锁，避免并发重复抓取）
# 用时间戳而非"当天已尝试"：抓不到新数据时必须还能重试，否则会卡住一整天（见 refresh_if_stale）
_refresh_lock = threading.Lock()
_refresh_marker = {'ts': 0.0}
_REFRESH_MIN_INTERVAL = 1800  # 两次后台抓取的最小间隔（秒）


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
    """页面加载时调用：若 K 线落后，则触发一次后台增量抓取（不阻塞请求）。

    节流用「时间戳 + 是否已追上」，而不是「当天是否已尝试」。原先按本地日期一天只试
    一次，在 UTC+8 会稳定丢一根 K 线：

      Binance 日 K 按 UTC 日切分，今天这根要到 UTC 00:00（本地 08:00）才收盘。
      本地 00:00–08:00 触发时 UTC 还停在昨天，昨天那根尚未收盘会被 fetch_binance
      丢弃 —— 抓不到任何新数据，却已把当天标记成"已尝试"，于是当天不再重试，
      那根 K 线要等到第二天才补上，天天差一根。

    因此：目标对齐到 UTC 昨天（今天那根还没走完，本就抓不到），没追上就允许按
    _REFRESH_MIN_INTERVAL 重试。

    返回是否启动了后台刷新。
    """
    # 今天这根 UTC 日 K 还没收盘，能拿到的最新一根是 UTC 昨天
    target = (datetime.now(timezone.utc) - timedelta(days=1)).strftime('%Y-%m-%d')
    with _refresh_lock:
        maxk = _latest_kline_date()
        if maxk and maxk >= target:
            return False                      # 已追上，无需抓取
        now = time.time()
        if now - _refresh_marker['ts'] < _REFRESH_MIN_INTERVAL:
            return False                      # 刚抓过，节流
        _refresh_marker['ts'] = now
    threading.Thread(target=_refresh_worker, daemon=True).start()
    return True


def _refresh_worker():
    """后台抓取。失败必须留痕：原先 verbose=False 跑在 daemon 线程里，
    任何异常或跳过都无声无息，K 线停更时无从排查。"""
    try:
        summary = fetch_all(verbose=False)
        skipped = (summary or {}).get('skipped') or []
        if skipped:
            print(f"[fetch_kline] 后台抓取完成，{len(skipped)} 个标的跳过: "
                  f"{', '.join(skipped[:10])}{' ...' if len(skipped) > 10 else ''}",
                  file=sys.stderr, flush=True)
    except Exception as e:
        print(f"[fetch_kline] 后台抓取失败: {type(e).__name__}: {e}",
              file=sys.stderr, flush=True)


def main():
    if not DB_PATH.exists():
        print(f"错误：数据库不存在 - {DB_PATH}")
        sys.exit(1)
    fetch_all(only=sys.argv[1:] or None, verbose=True)


if __name__ == '__main__':
    main()
