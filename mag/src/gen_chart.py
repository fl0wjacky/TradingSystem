#!/usr/bin/env python3
"""
生成标的可视化页面（mag_chart.html）

将 coin_daily_data 里每个标的的进/退场期、场外指数、爆破指数、谢林点导出为
一个自包含的 HTML 页面，用 ECharts 渲染：
  - 顶部面板：谢林点（价格参考，数据稀疏处自动连线）
  - 中部面板：场外指数（含 1000 均衡线、1500 参考线）
  - 底部面板：爆破指数（含 200、0 关键阈值线）
  - 进场期/退场期以背景色块贯穿三个面板
  - 逼近日以标记点提示
  - 三个面板 X 轴联动、共享缩放与十字光标

注：数据库中没有真实 OHLC，故用谢林点作价格代理。若日后接入外部行情源
（加密走交易所 API、美股/A股各自数据源），可在顶部面板叠加真实日 K 线。
"""
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'mag_data.db'
OUT_PATH = Path(__file__).parent.parent / 'mag_chart.html'


def load_data(db_path: Path) -> dict:
    """从数据库读取每个标的的时间序列，并计算进/退场期连续区间"""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT date, coin, phase_type, phase_days,
                   offchain_index, break_index, shelin_point,
                   is_approaching, is_us_stock, is_cn_stock, is_dragon_leader
            FROM coin_daily_data
            ORDER BY coin, date
        """).fetchall()

    by_coin: dict = {}
    for r in rows:
        by_coin.setdefault(r['coin'], []).append(r)

    series = {}
    for coin, recs in by_coin.items():
        dates = [r['date'] for r in recs]
        phase = [r['phase_type'] for r in recs]

        # 计算进/退场期的连续区间（用于背景着色）
        segments = []
        i = 0
        n = len(recs)
        while i < n:
            p = phase[i]
            j = i
            while j + 1 < n and phase[j + 1] == p:
                j += 1
            if p:  # 跳过 phase 为空的段
                segments.append({'phase': p, 'start': dates[i], 'end': dates[j]})
            i = j + 1

        r0 = recs[0]
        if r0['is_cn_stock']:
            kind = '国内A股'
        elif r0['is_us_stock']:
            kind = '美股/大宗'
        elif r0['is_dragon_leader']:
            kind = '龙头币'
        elif coin == 'BTC':
            kind = 'BTC'
        else:
            kind = '山寨币'

        series[coin] = {
            'kind': kind,
            'dates': dates,
            'phase': phase,
            'phase_days': [r['phase_days'] for r in recs],
            'offchain': [r['offchain_index'] for r in recs],
            'break': [r['break_index'] for r in recs],
            'shelin': [r['shelin_point'] for r in recs],
            'approaching': [i for i, r in enumerate(recs) if r['is_approaching']],
            'segments': segments,
        }

    # 排序：BTC、龙头币、美股/大宗、国内A股、山寨币
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
  select { background: #1a1d26; color: #eaecef; border: 1px solid #363b48;
           border-radius: 6px; padding: 6px 10px; font-size: 14px; min-width: 140px; }
  input[type=text] { background: #1a1d26; color: #eaecef; border: 1px solid #363b48;
           border-radius: 6px; padding: 6px 10px; font-size: 14px; width: 130px; }
  .legend { font-size: 12px; color: #8b91a0; display: flex; gap: 14px; flex-wrap: wrap; }
  .legend b { color: #b9bec9; font-weight: 600; }
  .sw { display: inline-block; width: 22px; height: 10px; border-radius: 2px; vertical-align: middle; margin-right: 4px; }
  #chart { width: 100%; height: calc(100vh - 58px); }
  .tag { font-size: 11px; padding: 1px 7px; border-radius: 10px; background: #232734; color: #9aa1b1; }
</style>
</head>
<body>
<header>
  <h1>Mag 标的可视化</h1>
  <select id="coinSel"></select>
  <input type="text" id="filter" placeholder="筛选标的…">
  <span class="tag" id="kindTag"></span>
  <span class="legend">
    <span><span class="sw" style="background:rgba(46,160,88,.22)"></span>进场期</span>
    <span><span class="sw" style="background:rgba(210,70,70,.22)"></span>退场期</span>
    <span><b>谢林点</b> 价格参考</span>
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

  // 进/退场期背景色块
  const areas = s.segments.map(seg => ([
    { xAxis: seg.start, itemStyle: { color: seg.phase === '进场期'
        ? 'rgba(46,160,88,0.13)' : 'rgba(210,70,70,0.13)' } },
    { xAxis: seg.end }
  ]));

  // 逼近标记点（放在场外指数面板上）
  const approachPts = s.approaching.map(i => ({
    xAxis: dates[i], yAxis: s.offchain[i],
    value: '逼近', symbol: 'triangle', symbolSize: 10,
    itemStyle: { color: '#e0a030' }
  }));

  return {
    animation: false,
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'cross', link: [{ xAxisIndex: 'all' }] },
      backgroundColor: 'rgba(20,23,31,0.95)', borderColor: '#363b48',
      textStyle: { color: '#d5d8df' },
      formatter: function (ps) {
        if (!ps.length) return '';
        const idx = ps[0].dataIndex;
        const ph = s.phase[idx] || '-';
        const pd = s.phase_days[idx];
        let html = '<b>' + dates[idx] + '</b>　<span style="color:' +
          (ph === '进场期' ? '#3fbf6a' : (ph === '退场期' ? '#e06666' : '#8b91a0')) +
          '">' + ph + (pd ? ' 第' + pd + '天' : '') + '</span><br>';
        const put = (name, v, unit) => { if (v !== null && v !== undefined)
          html += name + '：<b>' + v + (unit || '') + '</b><br>'; };
        put('谢林点', s.shelin[idx]);
        put('场外指数', s.offchain[idx]);
        put('爆破指数', s.break[idx]);
        return html;
      }
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }], label: { backgroundColor: '#363b48' } },
    grid: [
      { left: 62, right: 24, top: 20,  height: '40%' },
      { left: 62, right: 24, top: '52%', height: '20%' },
      { left: 62, right: 24, top: '76%', height: '17%' }
    ],
    xAxis: [
      { type: 'category', data: dates, gridIndex: 0, boundaryGap: false,
        axisLine: { lineStyle: { color: '#3a3f4d' } }, axisLabel: { show: false } },
      { type: 'category', data: dates, gridIndex: 1, boundaryGap: false,
        axisLine: { lineStyle: { color: '#3a3f4d' } }, axisLabel: { show: false }, axisTick: { show: false } },
      { type: 'category', data: dates, gridIndex: 2, boundaryGap: false,
        axisLine: { lineStyle: { color: '#3a3f4d' } }, axisLabel: { color: '#8b91a0', fontSize: 11 } }
    ],
    yAxis: [
      { scale: true, gridIndex: 0, name: '谢林点', nameTextStyle: { color: '#8b91a0' },
        splitLine: { lineStyle: { color: '#20242e' } }, axisLabel: { color: '#8b91a0' } },
      { scale: true, gridIndex: 1, name: '场外', nameTextStyle: { color: '#8b91a0' },
        splitLine: { lineStyle: { color: '#20242e' } }, axisLabel: { color: '#8b91a0' } },
      { scale: true, gridIndex: 2, name: '爆破', nameTextStyle: { color: '#8b91a0' },
        splitLine: { lineStyle: { color: '#20242e' } }, axisLabel: { color: '#8b91a0' } }
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2], start: 60, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1, 2], bottom: 4, height: 16,
        borderColor: '#363b48', fillerColor: 'rgba(90,120,180,0.2)',
        textStyle: { color: '#8b91a0' } }
    ],
    series: [
      { name: '谢林点', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: s.shelin,
        connectNulls: true, showSymbol: false, lineStyle: { color: '#c9a24a', width: 1.4 },
        markArea: { silent: true, data: areas } },
      { name: '场外指数', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: s.offchain,
        showSymbol: false, lineStyle: { color: '#4a90d9', width: 1.4 },
        markArea: { silent: true, data: areas },
        markLine: { silent: true, symbol: 'none',
          data: [
            { yAxis: 1000, lineStyle: { color: '#6a7180', type: 'solid' },
              label: { color: '#8b91a0', formatter: '1000' } },
            { yAxis: 1500, lineStyle: { color: '#3a3f4d', type: 'dashed' },
              label: { color: '#6a7180', formatter: '1500' } }
          ] },
        markPoint: { data: approachPts, label: { show: false } } },
      { name: '爆破指数', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: s.break,
        showSymbol: false, lineStyle: { color: '#b06fd0', width: 1.4 },
        markArea: { silent: true, data: areas },
        markLine: { silent: true, symbol: 'none',
          data: [
            { yAxis: 200, lineStyle: { color: '#c96a6a', type: 'dashed' },
              label: { color: '#c96a6a', formatter: '200' } },
            { yAxis: 0, lineStyle: { color: '#6a7180', type: 'solid' },
              label: { color: '#8b91a0', formatter: '0' } }
          ] } }
    ]
  };
}

function render(coin) {
  document.getElementById('kindTag').textContent = DATA.series[coin].kind;
  chart.setOption(buildOption(coin), true);
}

const sel = document.getElementById('coinSel');
function fillOptions(list) {
  sel.innerHTML = '';
  list.forEach(c => {
    const o = document.createElement('option');
    o.value = c; o.textContent = c + '  (' + DATA.series[c].kind + ')';
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

// 默认展示 BTC（或第一个）
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
    n_rows = sum(len(data['series'][c]['dates']) for c in data['coins'])
    print(f"✓ 已生成 {OUT_PATH}")
    print(f"  标的 {n_coins} 个，数据点 {n_rows} 条")
    print(f"  用浏览器打开即可（联动缩放需联网加载 ECharts）")


if __name__ == '__main__':
    main()
