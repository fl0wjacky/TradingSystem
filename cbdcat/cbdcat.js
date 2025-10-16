//@version=6
indicator("老猫2.0系统 - 彻底重构版", overlay=true, max_labels_count=500)

// ═══════════════════════════════════════════════════════════════════
// 📊 参数设置
// ═══════════════════════════════════════════════════════════════════
emaLength = input.int(37, "趋势EMA周期", minval=1)
atrLength = input.int(20, "ATR周期", minval=1)
atrMult = input.float(0.47, "ATR倍数", step=0.01, minval=0)
lookback = input.int(20, "结构判断回看周期", minval=1)

// ═══════════════════════════════════════════════════════════════════
// 📈 趋势通道计算
// ═══════════════════════════════════════════════════════════════════
emaMid = ta.ema(close, emaLength)
atrVal = ta.atr(atrLength)
upper = emaMid + atrMult * atrVal
lower = emaMid - atrMult * atrVal

plot(emaMid, "中轨", color=color.orange, linewidth=2)
plot(upper, "上轨", color=color.gray, linewidth=1)
plot(lower, "下轨", color=color.gray, linewidth=1)

// ═══════════════════════════════════════════════════════════════════
// 🎯 趋势状态判断（持续状态）
// ═══════════════════════════════════════════════════════════════════
var int trend = 0  // -1=下降趋势, 0=震荡, 1=上升趋势

// 检测趋势变化（在更新前）
trendUpBreak = close > upper and close[1] <= upper
trendDownBreak = close < lower and close[1] >= lower

// 价格突破上轨 → 上升趋势
if close > upper
    trend := 1
// 价格跌破下轨 → 下降趋势
else if close < lower
    trend := -1
// 否则保持原趋势不变

// 调试：绘制趋势突破点（可选）
// plotshape(trendUpBreak, "突破上轨", shape.diamond, location.belowbar, color.lime, size=size.normal)
// plotshape(trendDownBreak, "跌破下轨", shape.diamond, location.abovebar, color.maroon, size=size.normal)

// ═══════════════════════════════════════════════════════════════════
// 📐 MACD计算
// ═══════════════════════════════════════════════════════════════════
[macdLine, signalLine, hist] = ta.macd(close, 12, 26, 9)

// ═══════════════════════════════════════════════════════════════════
// 🔽 底部钝化与结构识别
// ═══════════════════════════════════════════════════════════════════
// 正负角线
positiveBar = close > close[1] and macdLine > macdLine[1]
negativeBar = close < close[1] and macdLine < macdLine[1]

// 底部钝化条件
twoNegBars = negativeBar and negativeBar[1]
// 价格创新低：当前最低价 <= 前lookback根K线的最低价
priceNewLow = low < ta.lowest(low[1], lookback)
// DIF不创新低：当前DIF >= 前lookback根K线的最低DIF
difNotNewLow = macdLine > ta.lowest(macdLine[1], lookback)
bottomDull = priceNewLow and difNotNewLow and twoNegBars

// 记录钝化状态（持久化）
var bool bottomDullActive = false
if bottomDull
    bottomDullActive := true

// 底部结构: 钝化活跃期间DIF拐头向上
bottomStruct = bottomDullActive and macdLine > macdLine[1] and macdLine[1] <= macdLine[2]

// 结构形成后清除钝化状态
if bottomStruct
    bottomDullActive := false

// 调试：绘制底部钝化和结构点
plotshape(bottomDull, "底部钝化", shape.circle, location.belowbar, color.blue, size=size.tiny)
plotshape(bottomStruct, "底部结构", shape.triangleup, location.belowbar, color.green, size=size.small)

// ═══════════════════════════════════════════════════════════════════
// 🔼 顶部钝化与结构识别
// ═══════════════════════════════════════════════════════════════════
// 顶部钝化条件
twoPosBars = positiveBar and positiveBar[1]
// 价格创新高：当前最高价 > 前lookback根K线的最高价
priceNewHigh = high > ta.highest(high[1], lookback)
// DIF不创新高：当前DIF < 前lookback根K线的最高DIF
difNotNewHigh = macdLine < ta.highest(macdLine[1], lookback)
topDull = priceNewHigh and difNotNewHigh and twoPosBars

// 记录钝化状态（持久化）
var bool topDullActive = false
if topDull
    topDullActive := true

// 顶部结构: 钝化活跃期间DIF拐头向下
topStruct = topDullActive and macdLine < macdLine[1] and macdLine[1] >= macdLine[2]

// 结构形成后清除钝化状态
if topStruct
    topDullActive := false

// 调试：绘制顶部钝化和结构点
plotshape(topDull, "顶部钝化", shape.circle, location.abovebar, color.purple, size=size.tiny)
plotshape(topStruct, "顶部结构", shape.triangledown, location.abovebar, color.red, size=size.small)

// ═══════════════════════════════════════════════════════════════════
// ⚠️ 纠错机制
// ═══════════════════════════════════════════════════════════════════
var float bottomRefDif = na
var float topRefDif = na

// 底部结构形成时,记录拐头前的DIF值
if bottomStruct
    bottomRefDif := macdLine[1]

// 顶部结构形成时,记录拐头前的DIF值
if topStruct
    topRefDif := macdLine[1]

// 底部纠错: DIF跌破参考值(钝化消失)
bottomCorrection = not na(bottomRefDif) and macdLine < bottomRefDif and macdLine[1] >= bottomRefDif

// 顶部纠错: DIF突破参考值(钝化消失)
topCorrection = not na(topRefDif) and macdLine > topRefDif and macdLine[1] <= topRefDif

// ═══════════════════════════════════════════════════════════════════
// 🔄 临时模式管理
// ═══════════════════════════════════════════════════════════════════
var bool tempMode = false
var int tempTrend = 0

// 趋势刚突破 + 出现钝化 → 进入临时模式
if (trendUpBreak or trendDownBreak) and (bottomDull or topDull)
    tempMode := true
    tempTrend := trendUpBreak ? 1 : -1

// 结构形成或纠错 → 退出临时模式
if bottomStruct or topStruct or bottomCorrection or topCorrection
    tempMode := false
    tempTrend := 0

// 调试：显示临时模式
bgcolor(tempMode ? color.new(color.yellow, 90) : na, title="临时模式")

// ═══════════════════════════════════════════════════════════════════
// 💰 仓位计算(完全按老猫系统规则)
// ═══════════════════════════════════════════════════════════════════
var float position = 0.0

// 趋势突破事件（不受临时模式影响）
if trendUpBreak
    position := 60.0
else if trendDownBreak
    position := 0.0
// 临时模式：暂不处理结构和纠错信号
else if not tempMode
    // 结构事件（在趋势内）
    if topStruct and trend == 1
        position := 40.0
    else if bottomStruct and trend == -1
        position := 40.0
    // 纠错事件
    else if topCorrection and trend == 1
        position := 60.0
    else if bottomCorrection and trend == -1
        position := 0.0
// 其他情况：保持原仓位

// ═══════════════════════════════════════════════════════════════════
// 🏷️ 标签生成
// ═══════════════════════════════════════════════════════════════════
var float lastPosition = 0.0

if position != lastPosition
    change = position - lastPosition
    labelText = ""

    // 趋势突破（优先显示）
    if trendUpBreak
        labelText := tempMode ? "🚀 趋势为上\n仓位60%\n⏸ 钝化中,暂停结构操作" : "🚀 趋势为上\n仓位60%"
    else if trendDownBreak
        labelText := tempMode ? "⚠️ 趋势为下\n清仓\n⏸ 钝化中,暂停结构操作" : "⚠️ 趋势为下\n清仓"
    // 结构信号
    else if bottomStruct
        labelText := "📈 底部结构\n加仓至40%"
    else if topStruct
        labelText := "📉 顶部结构\n减仓至40%"
    // 纠错信号
    else if bottomCorrection
        labelText := "🔧 底部纠错\n清仓"
    else if topCorrection
        labelText := "🔧 顶部纠错\n保持60%"
    // 其他仓位变化
    else
        labelText := (change > 0 ? "+" : "") + str.tostring(change, "#") + "%"

    // 绘制标签
    labelColor = change > 0 ? color.new(color.green, 0) : change < 0 ? color.new(color.red, 0) : color.new(color.gray, 0)
    labelStyle = change > 0 ? label.style_label_up : change < 0 ? label.style_label_down : label.style_label_center
    yPos = change > 0 ? low * 0.985 : change < 0 ? high * 1.015 : close

    label.new(bar_index, yPos, text=labelText,
             color=labelColor, textcolor=color.white,
             style=labelStyle, size=size.normal)

lastPosition := position

// ═══════════════════════════════════════════════════════════════════
// 🎨 通道填充
// ═══════════════════════════════════════════════════════════════════
p1 = plot(upper, display=display.none)
p2 = plot(lower, display=display.none)

bgColor = trend == 1 ? color.new(color.green, 92) : trend == -1 ? color.new(color.red, 92) : color.new(color.gray, 95)
fill(p1, p2, color=bgColor, title="趋势背景")

// ═══════════════════════════════════════════════════════════════════
// 🔔 警报
// ═══════════════════════════════════════════════════════════════════
alertcondition(position != position[1],
              title="仓位变动",
              message="{{ticker}} 仓位发生变动，请查看图表")

// ═══════════════════════════════════════════════════════════════════
// 📊 信息面板
// ═══════════════════════════════════════════════════════════════════
var table infoTable = table.new(position=position.top_right, columns=2, rows=4, bgcolor=color.new(color.black, 85), frame_color=color.gray, frame_width=1)

if barstate.islast
    // 当前仓位
    table.cell(infoTable, 0, 0, "当前仓位", text_color=color.white, bgcolor=color.new(color.blue, 50))
    table.cell(infoTable, 1, 0, str.tostring(position, "#") + "%",
              text_color=color.white, bgcolor=color.new(color.blue, 50))

    // 趋势状态
    table.cell(infoTable, 0, 1, "趋势状态", text_color=color.white)
    trendText = trend == 1 ? "上升" : trend == -1 ? "下降" : "震荡"
    trendColor = trend == 1 ? color.green : trend == -1 ? color.red : color.gray
    table.cell(infoTable, 1, 1, trendText, text_color=trendColor)

    // 特殊模式
    table.cell(infoTable, 0, 2, "模式", text_color=color.white)
    modeText = tempMode ? "临时模式" : "正常"
    table.cell(infoTable, 1, 2, modeText, text_color=tempMode ? color.yellow : color.white)

    // MACD状态
    table.cell(infoTable, 0, 3, "MACD", text_color=color.white)
    macdText = macdLine > 0 ? "多头" : "空头"
    table.cell(infoTable, 1, 3, macdText, text_color=macdLine > 0 ? color.green : color.red)