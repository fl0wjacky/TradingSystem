#!/usr/bin/env python3
"""
标的 -> 行情源映射

- 加密标的：Binance 现货 <COIN>USDT（免 key、稳定、历史长）
- 美股/ETF/商品/亚股：Binance 合约（fapi）代币化交易对，如 GOLD→XAUUSDT、
  NASDAQ→QQQUSDT、GOOG→GOOGLUSDT。免 key、不限流；但这些合约上线较晚，
  历史一般只回溯到 2026 年（个别更短），更早的日期无 K 线。
- 国内A股篮子（国内人工智能/机器人/生猪/地产等自定义标的）：无公开行情源，跳过

返回 (source, symbol)；未映射的标的返回 None（页面上仅显示场外/爆破，无 K 线）。
"""

# 加密：COIN -> Binance 现货交易对（不存在的会在抓取时被跳过，如 OKB/HYPE/PI）
CRYPTO = {
    c: c + 'USDT' for c in [
        'BTC', 'ETH', 'BNB', 'SOL', 'DOGE', 'ADA', 'AVAX', 'BCH', 'EOS', 'LTC',
        'LINK', 'UNI', 'CRV', 'LDO', 'AAVE', 'ONDO', 'PEPE', 'SEI', 'SUI', 'WLD',
        'ZEC', 'HYPE', 'TRUMP', 'PUMP', 'VIRTUAL', 'KAITO', 'OM', 'PI', 'RAY',
        'CFX', 'FLOKI', 'ARC', 'AI16Z', 'FARTCOIN', 'BGB', 'CET', 'OKB',
    ]
}

# 美股 / ETF / 商品 / 亚股：COIN -> Binance 合约(fapi)代币化交易对
STOCK_FUTURES = {
    # 美股
    'AAPL': 'AAPLUSDT', 'AMZN': 'AMZNUSDT', 'AAOI': 'AAOIUSDT', 'AXTI': 'AXTIUSDT',
    'BABA': 'BABAUSDT', 'CIRCLE': 'CRCLUSDT', 'COIN': 'COINUSDT', 'GLW': 'GLWUSDT',
    'GOOG': 'GOOGLUSDT', 'HOOD': 'HOODUSDT', 'MSFT': 'MSFTUSDT', 'MU': 'MUUSDT',
    'NVDA': 'NVDAUSDT', 'PLTR': 'PLTRUSDT', 'SNDK': 'SNDKUSDT', 'TSLA': 'TSLAUSDT',
    'NASDAQ': 'QQQUSDT',
    # 亚股
    '台积电': 'TSMUSDT', '海力士': 'SKHYNIXUSDT', '三星电子': 'SAMSUNGUSDT',
    # 商品
    'GOLD': 'XAUUSDT', 'OIL': 'CLUSDT', '白银': 'XAGUSDT', '铜': 'COPPERUSDT',
}


def get_source(coin: str):
    """返回 (source, symbol)；无行情源返回 None"""
    if coin in CRYPTO:
        return ('binance', CRYPTO[coin])
    if coin in STOCK_FUTURES:
        return ('binance_futures', STOCK_FUTURES[coin])
    return None
