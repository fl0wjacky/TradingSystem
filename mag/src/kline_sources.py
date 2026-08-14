#!/usr/bin/env python3
"""
标的 -> 行情源映射

- 加密标的：走 Binance 现货 <COIN>USDT（免 key、稳定）
- 美股/商品/亚股：走 Yahoo Finance（需未被限流的网络）
- 国内A股篮子（国内人工智能/机器人/生猪/地产 等自定义标的）：无公开行情源，跳过

返回 (source, symbol)；未映射的标的返回 None（页面上仅显示场外/爆破，无 K 线）。
"""

# 加密：COIN -> Binance 交易对（不存在的会在抓取时被跳过，如 OKB/BGB/CET）
CRYPTO = {
    c: c + 'USDT' for c in [
        'BTC', 'ETH', 'BNB', 'SOL', 'DOGE', 'ADA', 'AVAX', 'BCH', 'EOS', 'LTC',
        'LINK', 'UNI', 'CRV', 'LDO', 'AAVE', 'ONDO', 'PEPE', 'SEI', 'SUI', 'WLD',
        'ZEC', 'HYPE', 'TRUMP', 'PUMP', 'VIRTUAL', 'KAITO', 'OM', 'PI', 'RAY',
        'CFX', 'FLOKI', 'ARC', 'AI16Z', 'FARTCOIN', 'BGB', 'CET', 'OKB',
    ]
}

# 美股 / 商品 / 亚股：COIN -> Yahoo Finance ticker
YAHOO = {
    # 美股
    'AAPL': 'AAPL', 'AMZN': 'AMZN', 'AAOI': 'AAOI', 'AXTI': 'AXTI', 'BABA': 'BABA',
    'CIRCLE': 'CRCL', 'COIN': 'COIN', 'GLW': 'GLW', 'GOOG': 'GOOG', 'HOOD': 'HOOD',
    'MSFT': 'MSFT', 'MU': 'MU', 'NVDA': 'NVDA', 'PLTR': 'PLTR', 'SNDK': 'SNDK',
    'TSLA': 'TSLA', 'NASDAQ': '^IXIC',
    # 亚股
    '台积电': 'TSM', '海力士': '000660.KS', '三星电子': '005930.KS',
    # 商品（期货连续合约）
    'GOLD': 'GC=F', 'OIL': 'CL=F', '白银': 'SI=F', '铜': 'HG=F',
    # SPCX(SpaceX 未上市)、期权波动率、国内篮子等：无源，不列入
}


def get_source(coin: str):
    """返回 (source, symbol)；无行情源返回 None"""
    if coin in CRYPTO:
        return ('binance', CRYPTO[coin])
    if coin in YAHOO:
        return ('yahoo', YAHOO[coin])
    return None
