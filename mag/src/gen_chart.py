#!/usr/bin/env python3
"""
生成标的可视化页面（mag_chart.html）

将 coin_daily_data（进/退场期、场外指数、爆破指数）与 kline_data（真实日 K 线）
合并，导出为自包含 HTML，用 ECharts 渲染：
  - 顶部面板：真实日 K 线（蜡烛图，来自 kline_data；无行情源的标的自动隐藏此面板）
  - 中部面板：场外指数（含 1000 均衡线、1500 参考线）
  - 底部面板：爆破指数（含 200、0 关键阈值线）
  - 进场期/退场期以背景色块贯穿所有面板
  - 逼近日以标记点提示
  - X 轴为「K线交易日 ∪ 场外数据日」的并集，三面板联动缩放与十字光标

K 线数据由 src/fetch_kline.py 抓取（加密走 Binance，美股/商品/亚股走 Yahoo）。
先运行 fetch_kline 再运行本脚本，K 线才是最新的。
"""
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'mag_data.db'
OUT_PATH = Path(__file__).parent.parent / 'mag_chart.html'


def load_data(db_path: Path) -> dict:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cdd_rows = conn.execute("""
            SELECT date, coin, phase_type, phase_days, offchain_index, break_index,
                   is_approaching, is_us_stock, is_cn_stock, is_dragon_leader
            FROM coin_daily_data ORDER BY coin, date
        """).fetchall()
        # kline 表可能不存在
        kline = {}
        try:
            for r in conn.execute("SELECT date, coin, open, high, low, close FROM kline_data"):
                kline.setdefault(r[1], {})[r[0]] = (r[2], r[3], r[4], r[5])  # o,h,l,c
        except sqlite3.OperationalError:
            pass

    by_coin: dict = {}
    for r in cdd_rows:
        by_coin.setdefault(r['coin'], []).append(r)

    series = {}
    for coin, recs in by_coin.items():
        cdd = {r['date']: r for r in recs}
        kl = kline.get(coin, {})
        # X 轴 = 场外数据日 ∪ K线交易日
        dates = sorted(set(cdd) | set(kl))

        offchain, brk, phase, phase_days, ohlc, approaching = [], [], [], [], [], []
        for i, d in enumerate(dates):
            c = cdd.get(d)
            offchain.append(c['offchain_index'] if c else None)
            brk.append(c['break_index'] if c else None)
            phase.append(c['phase_type'] if c else None)
            phase_days.append(c['phase_days'] if c else None)
            if c and c['is_approaching']:
                approaching.append(i)
            if d in kl:
                o, h, l, cl = kl[d]
                ohlc.append([o, cl, l, h])  # ECharts 蜡烛图格式 [open, close, low, high]
            else:
                ohlc.append(None)

        # 进/退场期连续区间（仅取有场外数据的日子，按时间序）
        cdd_dates = [r['date'] for r in recs]
        cdd_phase = [r['phase_type'] for r in recs]
        segments, i, n = [], 0, len(recs)
        while i < n:
            p = cdd_phase[i]
            j = i
            while j + 1 < n and cdd_phase[j + 1] == p:
                j += 1
            if p:
                segments.append({'phase': p, 'start': cdd_dates[i], 'end': cdd_dates[j]})
            i = j + 1

        r0 = recs[0]
        kind = ('国内A股' if r0['is_cn_stock'] else '美股/大宗' if r0['is_us_stock']
                else '龙头币' if r0['is_dragon_leader'] else 'BTC' if coin == 'BTC' else '山寨币')

        series[coin] = {
            'kind': kind, 'dates': dates,
            'offchain': offchain, 'break': brk,
            'phase': phase, 'phase_days': phase_days,
            'ohlc': ohlc, 'hasKline': any(x is not None for x in ohlc),
            'approaching': approaching, 'segments': segments,
        }

    order = {'BTC': 0, '龙头币': 1, '美股/大宗': 2, '国内A股': 3, '山寨币': 4}
    coins = sorted(series.keys(), key=lambda c: (order.get(series[c]['kind'], 9), c))
    return {'coins': coins, 'series': series}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mag 标的可视化</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #0f1117; color: #d5d8df; }
  header { padding: 12px 18px; display: flex; align-items: center; gap: 14px;
           border-bottom: 1px solid #262a35; flex-wrap: wrap; }
  header h1 { font-size: 16px; margin: 0; font-weight: 600; color: #eaecef; }
  select, input[type=text] { background: #1a1d26; color: #eaecef; border: 1px solid #363b48;
           border-radius: 6px; padding: 6px 10px; font-size: 14px; }
  select { min-width: 150px; } input[type=text] { width: 130px; }
  .legend { font-size: 12px; color: #8b91a0; display: flex; gap: 14px; flex-wrap: wrap; }
  .legend b { color: #b9bec9; font-weight: 600; }
  .sw { display: inline-block; width: 22px; height: 10px; border-radius: 2px; vertical-align: middle; margin-right: 4px; }
  #chart { width: 100%; height: calc(100vh - 58px); }
  .tag { font-size: 11px; padding: 1px 7px; border-radius: 10px; background: #232734; color: #9aa1b1; }
  .nokl { color: #8b91a0; }
</style>
</head>
<body>
<header>
  <h1>Mag 标的可视化</h1>
  <select id="coinSel"></select>
  <input type="text" id="filter" placeholder="筛选标的…">
  <span class="tag" id="kindTag"></span>
  <span class="tag nokl" id="klTag"></span>
  <span class="legend">
    <span><span class="sw" style="background:rgba(46,160,88,.22)"></span>进场期</span>
    <span><span class="sw" style="background:rgba(210,70,70,.22)"></span>退场期</span>
    <span><b>K线</b> 涨绿跌红</span>
    <span><b>场外</b> 1000 均衡线</span>
    <span><b>爆破</b> 200 / 0 阈值</span>
    <span>▲ 逼近</span>
  </span>
</header>
<div id="chart"></div>
<script>
const DATA = __DATA__;
const chart = echarts.init(document.getElementById('chart'), 'dark');

function buildOption(coin) {
  const s = DATA.series[coin];
  const dates = s.dates;
  const kl = s.hasKline;

  const areaColor = ph => ph === '进场期' ? 'rgba(46,160,88,0.13)' : 'rgba(210,70,70,0.13)';
  const areas = s.segments.map(seg => ([
    { xAxis: seg.start, itemStyle: { color: areaColor(seg.phase) } }, { xAxis: seg.end }
  ]));
  const approachPts = s.approaching.map(i => ({
    xAxis: dates[i], yAxis: s.offchain[i], symbol: 'triangle', symbolSize: 10,
    itemStyle: { color: '#e0a030' }
  }));

  // 面板布局：有K线=3栏，无K线=2栏
  const grids = kl ? [
      { left: 62, right: 24, top: 20, height: '40%' },
      { left: 62, right: 24, top: '52%', height: '20%' },
      { left: 62, right: 24, top: '76%', height: '17%' }
    ] : [
      { left: 62, right: 24, top: 20, height: '40%' },
      { left: 62, right: 24, top: '56%', height: '34%' }
    ];
  const nGrid = grids.length;
  const offGrid = kl ? 1 : 0, brkGrid = kl ? 2 : 1;

  const mkX = (gi, showLabel) => ({ type: 'category', data: dates, gridIndex: gi,
    boundaryGap: kl, axisLine: { lineStyle: { color: '#3a3f4d' } },
    axisTick: { show: showLabel }, axisLabel: showLabel ? { color: '#8b91a0', fontSize: 11 } : { show: false } });
  const mkY = (gi, name) => ({ scale: true, gridIndex: gi, name: name,
    nameTextStyle: { color: '#8b91a0' }, splitLine: { lineStyle: { color: '#20242e' } },
    axisLabel: { color: '#8b91a0' } });

  const xAxis = [], yAxis = [], series = [];
  if (kl) { xAxis.push(mkX(0, false)); yAxis.push(mkY(0, 'K线')); }
  xAxis.push(mkX(offGrid, false)); yAxis.push(mkY(offGrid, '场外'));
  xAxis.push(mkX(brkGrid, true));  yAxis.push(mkY(brkGrid, '爆破'));

  const allX = Array.from({length: nGrid}, (_, i) => i);

  if (kl) {
    series.push({ name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0, data: s.ohlc,
      itemStyle: { color: '#26a06a', color0: '#d24646', borderColor: '#26a06a', borderColor0: '#d24646' },
      markArea: { silent: true, data: areas } });
  }
  series.push({ name: '场外指数', type: 'line', xAxisIndex: offGrid, yAxisIndex: offGrid,
    data: s.offchain, connectNulls: true, showSymbol: false, lineStyle: { color: '#4a90d9', width: 1.4 },
    markArea: { silent: true, data: areas },
    markLine: { silent: true, symbol: 'none', data: [
      { yAxis: 1000, lineStyle: { color: '#6a7180' }, label: { color: '#8b91a0', formatter: '1000' } },
      { yAxis: 1500, lineStyle: { color: '#3a3f4d', type: 'dashed' }, label: { color: '#6a7180', formatter: '1500' } } ] },
    markPoint: { data: approachPts, label: { show: false } } });
  series.push({ name: '爆破指数', type: 'line', xAxisIndex: brkGrid, yAxisIndex: brkGrid,
    data: s.break, connectNulls: true, showSymbol: false, lineStyle: { color: '#b06fd0', width: 1.4 },
    markArea: { silent: true, data: areas },
    markLine: { silent: true, symbol: 'none', data: [
      { yAxis: 200, lineStyle: { color: '#c96a6a', type: 'dashed' }, label: { color: '#c96a6a', formatter: '200' } },
      { yAxis: 0, lineStyle: { color: '#6a7180' }, label: { color: '#8b91a0', formatter: '0' } } ] } });

  return {
    animation: false, backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross', link: [{ xAxisIndex: 'all' }] },
      backgroundColor: 'rgba(20,23,31,0.95)', borderColor: '#363b48', textStyle: { color: '#d5d8df' },
      formatter: function (ps) {
        if (!ps.length) return '';
        const idx = ps[0].dataIndex;
        const ph = s.phase[idx] || '-', pd = s.phase_days[idx];
        let html = '<b>' + dates[idx] + '</b>　<span style="color:' +
          (ph === '进场期' ? '#3fbf6a' : (ph === '退场期' ? '#e06666' : '#8b91a0')) +
          '">' + ph + (pd ? ' 第' + pd + '天' : '') + '</span><br>';
        const o = s.ohlc[idx];
        if (o) html += '开' + o[0] + ' 高' + o[3] + ' 低' + o[2] + ' 收<b>' + o[1] + '</b><br>';
        const put = (nm, v) => { if (v !== null && v !== undefined) html += nm + '：<b>' + v + '</b><br>'; };
        put('场外指数', s.offchain[idx]); put('爆破指数', s.break[idx]);
        return html;
      } },
    axisPointer: { link: [{ xAxisIndex: 'all' }], label: { backgroundColor: '#363b48' } },
    grid: grids, xAxis: xAxis, yAxis: yAxis,
    dataZoom: [
      { type: 'inside', xAxisIndex: allX, start: 60, end: 100 },
      { type: 'slider', xAxisIndex: allX, bottom: 4, height: 16, borderColor: '#363b48',
        fillerColor: 'rgba(90,120,180,0.2)', textStyle: { color: '#8b91a0' } }
    ],
    series: series
  };
}

function render(coin) {
  const s = DATA.series[coin];
  document.getElementById('kindTag').textContent = s.kind;
  document.getElementById('klTag').textContent = s.hasKline ? '' : '无K线源';
  chart.setOption(buildOption(coin), true);
}

const sel = document.getElementById('coinSel');
function fillOptions(list) {
  sel.innerHTML = '';
  list.forEach(c => {
    const o = document.createElement('option');
    o.value = c;
    o.textContent = c + '  (' + DATA.series[c].kind + ')' + (DATA.series[c].hasKline ? ' 📈' : '');
    sel.appendChild(o);
  });
}
fillOptions(DATA.coins);
sel.addEventListener('change', () => render(sel.value));
document.getElementById('filter').addEventListener('input', e => {
  const q = e.target.value.trim().toUpperCase();
  const list = DATA.coins.filter(c => c.toUpperCase().includes(q));
  fillOptions(list.length ? list : DATA.coins);
  render(sel.value);
});
window.addEventListener('resize', () => chart.resize());

sel.value = DATA.coins.includes('BTC') ? 'BTC' : DATA.coins[0];
render(sel.value);
</script>
</body>
</html>
"""


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_PATH
    if not db_path.exists():
        print(f"错误：数据库不存在 - {db_path}")
        sys.exit(1)

    data = load_data(db_path)
    html = HTML_TEMPLATE.replace('__DATA__', json.dumps(data, ensure_ascii=False))
    OUT_PATH.write_text(html, encoding='utf-8')

    n_coins = len(data['coins'])
    n_kl = sum(1 for c in data['coins'] if data['series'][c]['hasKline'])
    print(f"✓ 已生成 {OUT_PATH}")
    print(f"  标的 {n_coins} 个，其中 {n_kl} 个含真实 K 线")
    print(f"  用浏览器打开即可（需联网加载 ECharts）")


if __name__ == '__main__':
    main()
