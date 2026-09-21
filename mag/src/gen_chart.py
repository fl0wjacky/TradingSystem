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
  - 关键节点（进/退场期第1天、爆破跌破200、爆破负转正）以彩色圆点标在场外指数线上，
    特殊节点以小灰点标出；悬停任一日期时列出当天所有节点的详情（类型、质量、修正后涨幅、
    参考节点、各项修正），便于复盘；回测的买卖点也落在这些节点上
  - X 轴为「K线交易日 ∪ 场外数据日」的并集，三面板联动缩放与十字光标
  - 回测（仅 API 实时页）：选日期范围与性格，按真实 K 线中间价 (开+收)/2 成交，
    买卖点标在 K 线上、资金曲线叠加在 K 线面板右轴，顶部条显示收益/回撤/交易明细

K 线数据由 src/fetch_kline.py 抓取（加密走 Binance 现货/合约，美股/商品/亚股走 Binance 合约）。
先运行 fetch_kline 再运行本脚本，K 线才是最新的。
"""
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / 'mag_data.db'
OUT_PATH = Path(__file__).parent.parent / 'mag_chart.html'


def load_nodes(conn, coin: str = None) -> dict:
    """关键节点（analysis_results）与特殊节点（special_nodes），按 coin -> date 归组。

    传 coin 只取该标的（供 /chart/nodes 按标的懒加载）；不传取全部（静态导出内嵌）。
    """
    where, params = ('WHERE coin = ?', (coin,)) if coin else ('', ())
    nodes: dict = {}
    for r in conn.execute(f"""
        SELECT date, coin, node_type, quality_rating, final_percentage,
               reference_node_date, reference_offchain_index, current_offchain_index,
               change_percentage, phase_correction, us_stock_correction,
               divergence_correction, break_index_correction, approaching_correction
        FROM analysis_results {where} ORDER BY coin, date, id""", params):
        corr = {k: v for k, v in (('相变', r[9]), ('美股', r[10]), ('背离', r[11]),
                                  ('爆破', r[12]), ('逼近', r[13])) if v}
        nodes.setdefault(r['coin'], {}).setdefault(r['date'], []).append({
            'kind': 'key', 'type': r['node_type'], 'quality': r['quality_rating'],
            'final_pct': r['final_percentage'], 'ref_date': r['reference_node_date'],
            'ref_idx': r['reference_offchain_index'], 'cur_idx': r['current_offchain_index'],
            'raw_pct': r['change_percentage'], 'corr': corr,
        })
    for r in conn.execute(
            f"SELECT date, coin, node_type, description FROM special_nodes {where} ORDER BY coin, date, id",
            params):
        nodes.setdefault(r['coin'], {}).setdefault(r['date'], []).append({
            'kind': 'special', 'type': r['node_type'], 'desc': r['description'] or r['node_type'],
        })
    return nodes


def load_coin_nodes(coin: str, db_path: Path = DB_PATH) -> dict:
    """单个标的的节点 {date: [节点...]}"""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        return load_nodes(conn, coin).get(coin, {})


def load_data(db_path: Path = DB_PATH, include_nodes: bool = True) -> dict:
    """页面数据。include_nodes=False 时不内嵌节点详情（API 实时页按标的懒加载 /chart/nodes）"""
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
        nodes = load_nodes(conn) if include_nodes else {}

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
        if include_nodes:
            series[coin]['nodes'] = nodes.get(coin, {})  # date -> [节点...]；不内嵌时前端懒加载

    order = {'BTC': 0, '龙头币': 1, '美股/大宗': 2, '国内A股': 3, '山寨币': 4}
    coins = sorted(series.keys(), key=lambda c: (order.get(series[c]['kind'], 9), c))
    return {'coins': coins, 'series': series}


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mag 场外体系</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif;
         background: #0f1117; color: #d5d8df; }
  header { padding: 12px 18px; display: flex; align-items: center; gap: 14px;
           border-bottom: 1px solid #262a35; flex-wrap: wrap; }
  header h1 { font-size: 16px; margin: 0; font-weight: 600; color: #eaecef; }
  select, input[type=date] { background: #1a1d26; color: #eaecef; border: 1px solid #363b48;
           border-radius: 6px; padding: 6px 10px; font-size: 14px; color-scheme: dark; }
  select { min-width: 150px; } input[type=date] { width: 140px; }
  button { background: #2a3550; color: #cdd7ee; border: 1px solid #3a4a6b;
           border-radius: 6px; padding: 6px 12px; font-size: 14px; cursor: pointer; }
  button:hover { background: #354063; }
  button:disabled { opacity: .45; cursor: not-allowed; }
  #btCtl { display: flex; align-items: center; gap: 6px; padding-left: 10px; border-left: 1px solid #262a35;
           flex-wrap: wrap; min-width: 0; }
  #btCtl[hidden] { display: none; }
  #btCtl select { min-width: 0; }
  #btBar { display: flex; align-items: center; gap: 16px; padding: 6px 18px; font-size: 13px;
           background: #151822; border-bottom: 1px solid #262a35; flex-wrap: wrap; }
  #btBar .trades { flex-basis: 100%; }
  #btBar[hidden] { display: none; }
  #btBar b { color: #eaecef; }
  #btBar .up { color: #3fbf6a; } #btBar .dn { color: #e06666; }
  #btBar .trades { color: #8b91a0; font-size: 12px; }
  #btBar .trades span { display: inline-block; margin-right: 12px; }
  #btBar .trades .b { color: #3fbf6a; } #btBar .trades .s { color: #e06666; }
  #btBar .err { color: #e06666; }
  #btBar .note { flex-basis: 100%; color: #6a7180; font-size: 11px; line-height: 1.5; }
  #btBar .note b { color: #8b91a0; font-weight: 600; }
  #btBar .x { margin-left: auto; cursor: pointer; color: #8b91a0; }
  .legend { font-size: 12px; color: #8b91a0; display: flex; gap: 14px; flex-wrap: wrap; min-width: 0; }
  .legend b { color: #b9bec9; font-weight: 600; }
  .sw { display: inline-block; width: 22px; height: 10px; border-radius: 2px; vertical-align: middle; margin-right: 4px; }
  body { display: flex; flex-direction: column; height: 100vh; }
  #chart { width: 100%; flex: 1; min-height: 0; }
  .tag { font-size: 11px; padding: 1px 7px; border-radius: 10px; background: #232734; color: #9aa1b1; }
  .nokl { color: #8b91a0; }

  /* ── 窄屏(手机)──
     根因是 #btCtl 作为 header 的 flex item 默认 min-width:auto,被里面最长的
     option「中间型-a (美股/BTC/龙头)」撑到 ~520px,撑宽 header 和 body,
     导致 header 的 flex-wrap 按被撑大的宽度算折行、整页横向溢出。
     上面已给它 min-width:0 + flex-wrap;这里再把各控件压紧并重排。 */
  @media (max-width: 640px) {
    header { padding: 9px 12px; gap: 8px; }
    header h1 { font-size: 14px; }
    select, input[type=date], button { font-size: 13px; padding: 5px 8px; }
    select { min-width: 0; max-width: 46vw; }

    /* 回测控件独占整行,排成:[开始] ~ [结束] / [性格] [回测] */
    #btCtl { width: 100%; padding-left: 0; border-left: none; gap: 5px; }
    #btCtl input[type=date] { flex: 1 1 110px; width: auto; min-width: 0; }
    /* basis 必然大于第一行剩余空间,强制 select 带着按钮一起换到第二行。
       用固定值(如 140px)会撞上边界:两个日期占完后剩余恰好约 137px,
       select 勉强挤进第一行,把「回测」按钮顶出屏幕。92px = 按钮 + gap + 余量。*/
    #btCtl select { flex: 1 1 calc(100% - 92px); max-width: none; }
    #btCtl button { flex: 0 0 auto; }

    .legend { gap: 6px 10px; font-size: 11px; line-height: 1.5; }
    .legend > span { min-width: 0; }
    .sw { width: 16px; height: 8px; margin-right: 3px; }
    #btBar { padding: 6px 12px; gap: 10px; }
  }
</style>
</head>
<body>
<header>
  <h1>Mag 场外体系</h1>
  <select id="coinSel"></select>
  <button id="shareBtn">📷 分享</button>
  <span id="btCtl" hidden>
    <input type="date" id="btStart" title="回测开始日期">
    <span style="color:#6a7180">~</span>
    <input type="date" id="btEnd" title="回测结束日期">
    <select id="btPers" title="性格类型">
      <option value="conservative">高稳健型</option>
      <option value="aggressive">高风险型</option>
      <option value="middle_a">中间型-a (美股/BTC/龙头)</option>
      <option value="middle_b">中间型-b (懒人)</option>
      <option value="middle_c">中间型-c (性价比)</option>
      <option value="middle_d">中间型-d (a8资金)</option>
    </select>
    <button id="btBtn">▶ 回测</button>
  </span>
  <span class="tag" id="kindTag"></span>
  <span class="tag nokl" id="klTag"></span>
  <span class="legend">
    <span><span class="sw" style="background:rgba(46,160,88,.22)"></span>进场期</span>
    <span><span class="sw" style="background:rgba(210,70,70,.22)"></span>退场期</span>
    <span><b>K线</b> 绿涨红跌</span>
    <span><b>场外</b> 1000 均衡线</span>
    <span><b>爆破</b> 200 / 0 阈值</span>
    <span>▲ 逼近</span>
    <span><b>节点</b> <span style="color:#3fbf6a">●</span>进场 <span style="color:#e06666">●</span>退场 <span style="color:#f0a040">●</span>跌破200 <span style="color:#b06fd0">●</span>负转正 <span style="color:#8b91a0">·</span>特殊</span>
    <span><span class="sw" style="background:#e0c060"></span>资金曲线</span>
  </span>
</header>
<div id="btBar" hidden></div>
<div id="chart"></div>
<script>
function initChart(DATA) {
const chart = echarts.init(document.getElementById('chart'), 'dark');
const NARROW = () => window.innerWidth <= 640;   // 与 CSS 断点保持一致
const BT = { coin: null, result: null };   // 当前回测结果（仅对应 BT.coin）
const ACTION_TXT = { buy_full: '全仓', buy_30: '买30%', buy_20: '买20%', buy_40: '买40%',
  buy_all_remaining: '买剩余', sell_50: '卖50%', sell_all: '清仓' };
const NODE_TXT = { enter_phase_day1: '进场期第1天', exit_phase_day1: '退场期第1天',
  break_200: '爆破跌破200', break_0: '爆破负转正' };
const NODE_COLOR = { enter_phase_day1: '#3fbf6a', exit_phase_day1: '#e06666',
  break_200: '#f0a040', break_0: '#b06fd0' };
const QUALITY_COLOR = { '优质': '#3fbf6a', '一般': '#e0c060', '劣质': '#e06666' };
const fmtPct = v => (v === null || v === undefined) ? '' : (v >= 0 ? '+' : '') + v.toFixed(1) + '%';
// 一天的节点列表渲染为 tooltip 片段
function nodesHtml(list) {
  if (!list || !list.length) return '';
  let h = '<div style="margin-top:4px;padding-top:4px;border-top:1px solid #363b48">';
  list.forEach(n => {
    if (n.kind === 'key') {
      const qc = QUALITY_COLOR[n.quality] || '#8b91a0';
      h += '<span style="color:' + (NODE_COLOR[n.type] || '#8b91a0') + '">●</span> <b>' + (NODE_TXT[n.type] || n.type) + '</b>　' +
        '<span style="color:' + qc + '">' + (n.quality || '无') + (n.quality && n.quality !== '无' ? ' ' + fmtPct(n.final_pct) : '') + '</span><br>';
      if (n.ref_date) {
        const corr = Object.entries(n.corr || {}).map(([k, v]) => k + (v > 0 ? '+' : '') + v).join(' ');
        h += '<span style="color:#8b91a0;font-size:11px">　参考 ' + n.ref_date.slice(5) + ' 场外 ' + n.ref_idx + ' → ' + n.cur_idx +
          ' (' + fmtPct(n.raw_pct) + ')' + (corr ? ' · 修正 ' + corr : '') + '</span><br>';
      } else {
        h += '<span style="color:#8b91a0;font-size:11px">　无参考节点，无法计算质量</span><br>';
      }
    } else {
      h += '<span style="color:#8b91a0">·</span> <span style="color:#b9bec9">' + n.desc + '</span><br>';
    }
  });
  return h + '</div>';
}

function buildOption(coin) {
  const s = DATA.series[coin];
  const dates = s.dates;
  const kl = s.hasKline;
  const bt = (BT.coin === coin && BT.result) ? BT.result : null;

  const areaColor = ph => ph === '进场期' ? 'rgba(46,160,88,0.13)' : 'rgba(210,70,70,0.13)';
  const areas = s.segments.map(seg => ([
    { xAxis: seg.start, itemStyle: { color: areaColor(seg.phase) } }, { xAxis: seg.end }
  ]));
  const approachPts = s.approaching.map(i => ({
    xAxis: dates[i], yAxis: s.offchain[i], symbol: 'triangle', symbolSize: 10,
    itemStyle: { color: '#e0a030' }
  }));
  // 关键节点彩色圆点 / 特殊节点小灰点（逼近已有 ▲，不重复画）
  const nodePts = [];
  const nodesMap = s.nodes || {};   // 实时页按标的懒加载，未到达前为空
  dates.forEach((d, i) => {
    const list = nodesMap[d];
    if (!list || s.offchain[i] === null) return;
    const key = list.find(n => n.kind === 'key');
    if (key) {
      nodePts.push({ xAxis: d, yAxis: s.offchain[i], symbol: 'circle', symbolSize: 8,
        itemStyle: { color: NODE_COLOR[key.type] || '#8b91a0', borderColor: '#0f1117', borderWidth: 1 } });
    } else if (list.some(n => n.kind === 'special' && n.type !== 'approaching')) {
      nodePts.push({ xAxis: d, yAxis: s.offchain[i], symbol: 'circle', symbolSize: 4,
        itemStyle: { color: '#8b91a0', opacity: 0.8 } });
    }
  });

  // 面板布局：有K线=3栏，无K线=2栏；各面板间距一致且留足空间放轴名（均为 6%）
  // 窄屏收紧左右内边距:390px 下 62+58 会吃掉 31% 宽度,只剩 270px 画图
  const gL = NARROW() ? 50 : 62, gR = NARROW() ? 30 : 58;
  const grids = kl ? [
      { left: gL, right: gR, top: 28, height: '42.5%' },
      { left: gL, right: gR, top: '52%',  height: '17%' },
      { left: gL, right: gR, top: '75%',  height: '17%' }
    ] : [
      { left: gL, right: gR, top: 28,  height: '46%' },
      { left: gL, right: gR, top: '55.5%', height: '36.5%' }
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
  xAxis.push(mkX(offGrid, false)); yAxis.push(mkY(offGrid, '场外指数'));
  xAxis.push(mkX(brkGrid, true));  yAxis.push(mkY(brkGrid, '爆破指数'));

  const allX = Array.from({length: nGrid}, (_, i) => i);

  if (kl) {
    // 回测买卖点：买 ▲ 标在最低价下方，卖 ▼ 标在最高价上方
    const tradePts = bt ? bt.trades.map(t => {
      const i = dates.indexOf(t.date), o = s.ohlc[i] || [t.price, t.price, t.price, t.price];
      const buy = t.action.startsWith('buy');
      return { coord: [t.date, buy ? o[2] : o[3]], symbol: 'triangle', symbolSize: 12,
        symbolRotate: buy ? 0 : 180, symbolOffset: [0, buy ? 10 : -10],
        itemStyle: { color: buy ? '#3fbf6a' : '#e06666' },
        label: { show: true, position: buy ? 'bottom' : 'top', fontSize: 10,
          color: buy ? '#3fbf6a' : '#e06666', formatter: ACTION_TXT[t.action] || t.action } };
    }) : [];
    // 蜡烛图不接受 null 数据项(会读 null.value 报错),空档用 ECharts 空值标记 '-'
    series.push({ name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
      data: s.ohlc.map(x => x || '-'),
      itemStyle: { color: '#26a06a', color0: '#d24646', borderColor: '#26a06a', borderColor0: '#d24646' },
      markArea: { silent: true, data: areas },
      markPoint: { data: tradePts, silent: true } });
    if (bt) {
      // 资金曲线：K 线面板右轴
      const eq = new Map(bt.equity);
      yAxis.push({ gridIndex: 0, position: 'right', scale: true, name: '资金', nameTextStyle: { color: '#e0c060' },
        splitLine: { show: false }, axisLabel: { color: '#e0c060', fontSize: 10 } });
      series.push({ name: '资金曲线', type: 'line', xAxisIndex: 0, yAxisIndex: yAxis.length - 1,
        data: dates.map(d => eq.has(d) ? eq.get(d) : null), connectNulls: false, showSymbol: false,
        lineStyle: { color: '#e0c060', width: 1.2 }, z: 5 });
    }
  }
  series.push({ name: '场外指数', type: 'line', xAxisIndex: offGrid, yAxisIndex: offGrid,
    data: s.offchain, connectNulls: true, showSymbol: false, lineStyle: { color: '#4a90d9', width: 1.4 },
    markArea: { silent: true, data: areas },
    markLine: { silent: true, symbol: 'none', data: [
      { yAxis: 1000, lineStyle: { color: '#6a7180' }, label: { color: '#8b91a0', formatter: '1000' } },
      { yAxis: 1500, lineStyle: { color: '#3a3f4d', type: 'dashed' }, label: { color: '#6a7180', formatter: '1500' } } ] },
    markPoint: { data: nodePts.concat(approachPts), label: { show: false }, silent: true } });
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
        html += nodesHtml((s.nodes || {})[dates[idx]]);
        if (bt) {
          const d = dates[idx];
          bt.trades.filter(t => t.date === d).forEach(t => {
            const buy = t.action.startsWith('buy');
            html += '<span style="color:' + (buy ? '#3fbf6a' : '#e06666') + '">' +
              (ACTION_TXT[t.action] || t.action) + ' @ ' + t.price.toFixed(2) + '</span><br>';
          });
          const e = bt.equity.find(x => x[0] === d);
          if (e) html += '资金：<b style="color:#e0c060">' + e[1].toFixed(0) + '</b><br>';
        }
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
  if (BT.coin !== coin) clearBacktest(false);
  syncBtControls(coin);
  chart.setOption(buildOption(coin), true);
  if (DATA.live && !s.nodes) loadNodes(coin);
}

// 节点详情按标的懒加载（实时页 /chart/data 不内嵌，首次切到该标的时拉取并缓存）
const nodesLoading = new Set();
function loadNodes(coin, force) {
  if (nodesLoading.has(coin)) return;
  nodesLoading.add(coin);
  fetch('/chart/nodes?coin=' + encodeURIComponent(coin)).then(r => r.ok ? r.json() : {})
    .then(nodes => {
      DATA.series[coin].nodes = nodes;
      if (sel.value === coin) chart.setOption(buildOption(coin), true);  // 仍在看这个标的才刷新
    })
    .catch(() => { DATA.series[coin].nodes = DATA.series[coin].nodes || {}; })
    .finally(() => nodesLoading.delete(coin));
}

// ---- 回测（仅 API 实时页可用；静态导出无后端，隐藏控件）----
const btCtl = document.getElementById('btCtl'), btBar = document.getElementById('btBar');
const btStart = document.getElementById('btStart'), btEnd = document.getElementById('btEnd');
const btPers = document.getElementById('btPers'), btBtn = document.getElementById('btBtn');

function klineRange(coin) {
  const s = DATA.series[coin], ds = s.dates.filter((d, i) => s.ohlc[i]);
  return ds.length ? [ds[0], ds[ds.length - 1]] : null;
}
// 日期控件限定在该标的有 K 线的日期范围内；超出范围或为空时重置为整个范围
function syncBtControls(coin) {
  const r = klineRange(coin);
  btBtn.disabled = !r;
  btStart.disabled = btEnd.disabled = btPers.disabled = !r;
  if (!r) return;
  [btStart, btEnd].forEach(el => { el.min = r[0]; el.max = r[1]; });
  if (!btStart.value || btStart.value < r[0] || btStart.value > r[1]) btStart.value = r[0];
  if (!btEnd.value || btEnd.value > r[1] || btEnd.value < r[0]) btEnd.value = r[1];
}
function clearBacktest(redraw) {
  BT.coin = null; BT.result = null;
  btBar.hidden = true; btBar.innerHTML = '';
  chart.resize();
  if (redraw) chart.setOption(buildOption(sel.value), true);
}
function showBtBar(html) { btBar.innerHTML = html; btBar.hidden = false; chart.resize(); }
function fmtMoney(v) { return v.toLocaleString('en-US', { maximumFractionDigits: 0 }); }

async function runBacktest() {
  const coin = sel.value;
  if (btStart.value > btEnd.value) { showBtBar('<span class="err">开始日期不能晚于结束日期</span>'); return; }
  btBtn.disabled = true; btBtn.textContent = '分析+回测中…';
  try {
    const q = new URLSearchParams({ coin, start: btStart.value, end: btEnd.value, personality: btPers.value });
    const resp = await fetch('/chart/backtest?' + q);
    const body = await resp.json();
    if (!resp.ok) { clearBacktest(true); showBtBar('<span class="err">' + (body.detail || '回测失败') + '</span>'); return; }
    BT.coin = coin; BT.result = body;
    const persTxt = btPers.options[btPers.selectedIndex].text;
    const up = body.profit_rate >= 0;
    const trades = body.trades.map(t => {
      const buy = t.action.startsWith('buy');
      return '<span class="' + (buy ? 'b' : 's') + '">' + t.date.slice(5) + ' ' +
        (ACTION_TXT[t.action] || t.action) + ' @' + t.price.toFixed(t.price < 1 ? 4 : 2) + '</span>';
    }).join('');
    showBtBar(
      '<span><b>' + coin + '</b> · ' + persTxt + ' · ' + body.start_date + ' ~ ' + body.end_date + '</span>' +
      '<span>初始 <b>' + fmtMoney(body.initial_capital) + '</b> → 期末 <b>' + fmtMoney(body.final_value) + '</b></span>' +
      '<span>收益率 <b class="' + (up ? 'up' : 'dn') + '">' + (up ? '+' : '') + body.profit_rate.toFixed(2) + '%</b></span>' +
      '<span>最大回撤 <b class="dn">' + body.max_drawdown.toFixed(2) + '%</b></span>' +
      '<span>交易 <b>' + body.trades.length + '</b> 笔</span>' +
      '<span class="x" id="btClose" title="清除回测">✕</span>' +
      (body.trades.length ? '<span class="trades">' + trades + '</span>' : '<span class="trades">期间无交易</span>') +
      '<span class="note"><b>节点</b>：每次回测前先对该标的在所选区间重新分析节点（只重算这一个标的），回测结果始终基于当前数据与分析逻辑。' +
      '　<b>价格</b>：成交价取当日 K 线中间价 (开+收)/2，只在有 K 线的日期成交，无 K 线的节点跳过；资金曲线按每日中间价估值。' +
      '　<b>仓位</b>：买 20%/30%/40% 以下单当时的账户总市值（现金 + 持仓市值）为基数，不按初始资金、不累计；' +
      '超出剩余现金时只买剩余现金，现金用完后的买入信号跳过，因此多次分批名义比例可超 100%，实际投入不会超过账户资金。</span>');
    document.getElementById('btClose').addEventListener('click', () => clearBacktest(true));
    chart.setOption(buildOption(coin), true);
    delete DATA.series[coin].nodes; loadNodes(coin);  // 回测前重算了节点，刷新节点缓存
    // 视窗对准回测区间
    chart.dispatchAction({ type: 'dataZoom', startValue: body.start_date, endValue: body.end_date });
  } catch (e) {
    clearBacktest(true); showBtBar('<span class="err">回测请求失败：' + e.message + '</span>');
  } finally {
    btBtn.disabled = !klineRange(sel.value); btBtn.textContent = '▶ 回测';
  }
}
if (DATA.live) {
  btCtl.hidden = false;
  btBtn.addEventListener('click', runBacktest);
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
let _wasNarrow = NARROW();
window.addEventListener('resize', () => {
  chart.resize();
  // 只在跨越断点时重绘(转屏/改窗宽),平时仅 resize,避免丢 dataZoom 状态
  if (NARROW() !== _wasNarrow) { _wasNarrow = NARROW(); chart.setOption(buildOption(sel.value), true); }
});

// 分享：把当前图表合成为带标题的分享卡片 PNG 并下载
function exportImage() {
  const coin = sel.value, s = DATA.series[coin];
  const chartUrl = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#0f1117' });
  const img = new Image();
  img.onload = () => {
    const headerH = 128;  // 2x 像素空间
    const cv = document.createElement('canvas');
    cv.width = img.width; cv.height = img.height + headerH;
    const ctx = cv.getContext('2d');
    ctx.fillStyle = '#0f1117'; ctx.fillRect(0, 0, cv.width, cv.height);
    const lastDate = s.dates[s.dates.length - 1], firstDate = s.dates[0];
    ctx.textBaseline = 'alphabetic';
    ctx.fillStyle = '#eaecef';
    ctx.font = 'bold 40px -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif';
    ctx.fillText(coin + '　' + s.kind, 40, 60);
    ctx.fillStyle = '#8b91a0';
    ctx.font = '26px -apple-system, "PingFang SC", sans-serif';
    const bt = (BT.coin === coin && BT.result) ? BT.result : null;
    const btTxt = bt ? ('　回测 ' + btPers.options[btPers.selectedIndex].text + ' ' + bt.start_date + '~' + bt.end_date +
      ' 收益 ' + (bt.profit_rate >= 0 ? '+' : '') + bt.profit_rate.toFixed(1) + '% 回撤 ' + bt.max_drawdown.toFixed(1) + '%') : '';
    ctx.fillText('Mag 场外体系 · ' + firstDate + ' ~ ' + lastDate + btTxt, 40, 100);
    ctx.drawImage(img, 0, headerH);
    const a = document.createElement('a');
    a.download = 'Mag_' + coin + '_' + lastDate + '.png';
    a.href = cv.toDataURL('image/png');
    a.click();
  };
  img.src = chartUrl;
}
document.getElementById('shareBtn').addEventListener('click', exportImage);

sel.value = DATA.coins.includes('BTC') ? 'BTC' : DATA.coins[0];
render(sel.value);
}
__BOOTSTRAP__
</script>
</body>
</html>
"""


def render_page(bootstrap_js: str) -> str:
    """用给定的数据引导代码渲染完整 HTML 页面。

    - 静态文件：bootstrap 传入 `initChart(<内嵌JSON>)`
    - API 实时：bootstrap 传入 `fetch('/chart/data')...then(initChart)`，并置 `live=true`
      以启用回测控件（静态文件无后端，回测控件隐藏）
    """
    return HTML_TEMPLATE.replace('__BOOTSTRAP__', bootstrap_js)


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DB_PATH
    if not db_path.exists():
        print(f"错误：数据库不存在 - {db_path}")
        sys.exit(1)

    data = load_data(db_path)
    bootstrap = 'initChart(' + json.dumps(data, ensure_ascii=False) + ');'
    OUT_PATH.write_text(render_page(bootstrap), encoding='utf-8')

    n_coins = len(data['coins'])
    n_kl = sum(1 for c in data['coins'] if data['series'][c]['hasKline'])
    print(f"✓ 已生成 {OUT_PATH}")
    print(f"  标的 {n_coins} 个，其中 {n_kl} 个含真实 K 线")
    print(f"  用浏览器打开即可（需联网加载 ECharts）")


if __name__ == '__main__':
    main()
