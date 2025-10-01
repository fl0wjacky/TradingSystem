//@version=6
strategy("老猫2.0 - 完整版", overlay=true,
         initial_capital=10000,
         default_qty_type=strategy.percent_of_equity,
         commission_type=strategy.commission.percent,
         commission_value=0.1)

// ═══════════════════════════════════════════════════════════════════
// 📊 参数
// ═══════════════════════════════════════════════════════════════════
emaLength = input.int(37, "EMA周期")
atrLength = input.int(20, "ATR周期")
atrMult = input.float(0.47, "ATR倍数")
lookback = input.int(20, "结构回看周期")

// ═══════════════════════════════════════════════════════════════════
// 📈 趋势通道
// ═══════════════════════════════════════════════════════════════════
emaMid = ta.ema(close, emaLength)
atrVal = ta.atr(atrLength)
upper = emaMid + atrMult * atrVal
lower = emaMid - atrMult * atrVal

plot(emaMid, "中轨", color=color.orange, linewidth=2)
plot(upper, "上轨", color=color.gray)
plot(lower, "下轨", color=color.gray)

// ═══════════════════════════════════════════════════════════════════
// 🎯 趋势状态
// ═══════════════════════════════════════════════════════════════════
var int trend = 0  // -1=下降, 0=震荡, 1=上升

trendUpBreak = ta.crossover(close, upper)
trendDownBreak = ta.crossunder(close, lower)

if close > upper
    trend := 1
else if close < lower
    trend := -1

// ═══════════════════════════════════════════════════════════════════
// 📐 MACD
// ═══════════════════════════════════════════════════════════════════
[macdLine, signalLine, hist] = ta.macd(close, 12, 26, 9)

// 正负角线
positiveBar = close > close[1] and macdLine > macdLine[1]
negativeBar = close < close[1] and macdLine < macdLine[1]

// ═══════════════════════════════════════════════════════════════════
// 🔽 底部钝化与结构
// ═══════════════════════════════════════════════════════════════════
twoNegBars = negativeBar and negativeBar[1]
priceNewLow = low < ta.lowest(low[1], lookback)
difNotNewLow = macdLine > ta.lowest(macdLine[1], lookback)
bottomDull = priceNewLow and difNotNewLow and twoNegBars

var bool bottomDullActive = false
if bottomDull
    bottomDullActive := true

bottomStruct = bottomDullActive and macdLine > macdLine[1] and macdLine[1] <= macdLine[2]

if bottomStruct
    bottomDullActive := false

// ═══════════════════════════════════════════════════════════════════
// 🔼 顶部钝化与结构
// ═══════════════════════════════════════════════════════════════════
twoPosBars = positiveBar and positiveBar[1]
priceNewHigh = high > ta.highest(high[1], lookback)
difNotNewHigh = macdLine < ta.highest(macdLine[1], lookback)
topDull = priceNewHigh and difNotNewHigh and twoPosBars

var bool topDullActive = false
if topDull
    topDullActive := true

topStruct = topDullActive and macdLine < macdLine[1] and macdLine[1] >= macdLine[2]

if topStruct
    topDullActive := false

// ═══════════════════════════════════════════════════════════════════
// ⚠️ 纠错机制
// ═══════════════════════════════════════════════════════════════════
var float bottomRefDif = na
var float topRefDif = na

if bottomStruct
    bottomRefDif := macdLine[1]

if topStruct
    topRefDif := macdLine[1]

bottomCorrection = not na(bottomRefDif) and macdLine < bottomRefDif and macdLine[1] >= bottomRefDif
topCorrection = not na(topRefDif) and macdLine > topRefDif and macdLine[1] <= topRefDif

// ═══════════════════════════════════════════════════════════════════
// 💰 仓位计算
// ═══════════════════════════════════════════════════════════════════
var float targetPos = 0.0

// 趋势突破
if trendUpBreak
    targetPos := 100.0
else if trendDownBreak
    targetPos := 0.0
// 结构信号
else if topStruct and trend == 1
    targetPos := 60.0  // 减仓40%（从100%减到60%）
else if bottomStruct and trend == -1
    targetPos := 40.0  // 加仓40%（从0%加到40%）
// 纠错信号
else if topCorrection and trend == 1
    targetPos := 100.0  // 纠错：恢复满仓
else if bottomCorrection and trend == -1
    targetPos := 0.0   // 纠错：清仓

// ═══════════════════════════════════════════════════════════════════
// 📊 策略执行
// ═══════════════════════════════════════════════════════════════════
var float lastTargetPos = 0.0

if targetPos != lastTargetPos
    // 清仓
    if targetPos == 0 and strategy.position_size > 0
        strategy.close_all(comment="清仓")

    // 调整仓位
    else if targetPos > 0
        if strategy.position_size > 0
            strategy.close_all()
        strategy.entry("Long", strategy.long, qty=targetPos, comment="仓位" + str.tostring(targetPos, "#") + "%")

    lastTargetPos := targetPos

// ═══════════════════════════════════════════════════════════════════
// 🎨 可视化
// ═══════════════════════════════════════════════════════════════════
plotshape(trendUpBreak, "趋势上", shape.triangleup, location.belowbar, color.green, size=size.normal)
plotshape(trendDownBreak, "趋势下", shape.triangledown, location.abovebar, color.red, size=size.normal)
plotshape(bottomStruct, "底部结构", shape.circle, location.belowbar, color.blue, size=size.small)
plotshape(topStruct, "顶部结构", shape.circle, location.abovebar, color.purple, size=size.small)
plotshape(bottomCorrection, "底纠错", shape.xcross, location.belowbar, color.orange, size=size.tiny)
plotshape(topCorrection, "顶纠错", shape.xcross, location.abovebar, color.orange, size=size.tiny)

bgcolor(trend == 1 ? color.new(color.green, 95) : trend == -1 ? color.new(color.red, 95) : na)