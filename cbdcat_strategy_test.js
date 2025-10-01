//@version=6
strategy("老猫2.0 - 完整闭环版", overlay=true,
         initial_capital=10000,
         default_qty_type=strategy.percent_of_equity,
         default_qty_value=100,
         commission_type=strategy.commission.percent,
         commission_value=0.1,
         pyramiding=5)
 
// ═══════════════════════════════════════════════════════════════════
// 📊 参数
// ═══════════════════════════════════════════════════════════════════
emaLength = input.int(37, "EMA周期")
atrLength = input.int(20, "ATR周期")
atrMult = input.float(0.47, "ATR倍数")
lookback = input.int(20, "结构回看周期")
 
// ══════════════════════════════════════════════════════════════════
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
var int trend = 0 // -1=降, 0=震荡, 1=上升
 
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
// 🔽 底钝化与结构
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
// 📊 策略执行（直接信号驱动）
// ═══════════════════════════════════════════════════════════════════

// 1. 趋势突破上轨 → 满仓100%
if trendUpBreak
    strategy.entry("Long", strategy.long, comment="趋势上 100%")
 
// 2. 趋势跌破下轨 → 清仓
if trendDownBreak
    strategy.close_all(comment="趋势下 清仓")
 
// 3. 上升趋势中出现顶部结构 → 减仓40%（从100%减到60%）
if topStruct and trend == 1 and strategy.position_size > 0
    strategy.close("Long", qty_percent=40, comment="顶部结构 减仓40%")
 
// 4. 下降趋势中出现底部结构 → 加仓40%（从0%加到40%）
if bottomStruct and trend == -1
    strategy.entry("Long", strategy.long, qty=40, comment="底部结构 加40%")
 
// 5. 上升趋势中顶部纠错 → 目标再平衡到 100%
if topCorrection and trend == 1 and strategy.position_size > 0
    qty = (strategy.equity - strategy.position_size*close)/close
    strategy.entry("Long_rebal", strategy.long, qty=qty, comment="顶纠错 再平衡至100%")
 
// 6. 下降趋势中底部纠错 → 清仓
if bottomCorrection and trend == -1
    strategy.close_all(comment="底纠错 清仓")
 
// ═══════════════════════════════════════════════════════════════════
// 🎨 可视化
// ═══════════════════════════════════════════════════════════════════
plotshape(trendUpBreak, "趋势上", shape.triangleup, location.belowbar, color.green, size=size.normal,
 text="趋势上")
plotshape(trendDownBreak, "趋势下", shape.triangledown, location.abovebar, color.red, size=size.normal,
 text="趋势下")
plotshape(bottomStruct, "底部结构", shape.circle, location.belowbar, color.blue, size=size.small,
 text="底部")
plotshape(topStruct, "顶部结构", shape.circle, location.abovebar, color.purple, size=size.small,
 text="顶部")
plotshape(bottomCorrection, "底纠错", shape.xcross, location.belowbar, color.orange, size=size.tiny,
 text="底纠错")
plotshape(topCorrection, "顶纠错", shape.xcross, location.abovebar, color.orange, size=size.tiny,
 text="顶纠错")
 
bgcolor(trend == 1 ? color.new(color.green, 95) : trend == -1 ? color.new(color.red, 95) : na)
