//@version=6
strategy("老猫2.0 - 完整闭环版", overlay=true,
         initial_capital=10000,
         default_qty_type=strategy.percent_of_equity,
         default_qty_value=100,
         commission_type=strategy.commission.percent,
         commission_value=0.0,
         process_orders_on_close=true,   // ✅ 本根收盘撮合
         calc_on_order_fills=true,      // ✅ 同根先平后开
         pyramiding=5)

// ═══════════════════════════════════════════════════════════════════
// 🧰 级别选择（默认 L1）
// L1=趋势通道；L2=通道+结构；L3=通道+结构+纠错；L4=+特殊情况；L5=+多周期/序列(占位)
// ═══════════════════════════════════════════════════════════════════
level = input.int(0, "策略等级L0-L5）", minval=0, maxval=5,
     tooltip="L0=趋势通道；L1=趋势通道有震荡；L2=通道+结构；L3=通道+结构+纠错；L4=+特殊情况；L5=+多周期/序列(占位)")
enableL1 = level >= 1
enableL2 = level >= 2
enableL3 = level >= 3
enableL4 = level >= 4
enableL5 = level >= 5   // 预留，占位

// ═══════════════════════════════════════════════════════════════════
// 📊 参数
// ═══════════════════════════════════════════════════════════════════
emaLength = input.int(37, "EMA周期")
atrLength = input.int(20, "ATR周期")
atrMult   = input.float(0.47, "ATR倍数")
lookback  = input.int(20, "结构回看周期")

// ═══════════════════════════════════════════════════════════════════
// 📈 趋势通道
// ═══════════════════════════════════════════════════════════════════
emaMid = ta.ema(close, emaLength)
atrVal = ta.atr(atrLength)
upper  = emaMid + atrMult * atrVal
lower  = emaMid - atrMult * atrVal

plot(emaMid, "中轨", color=color.orange, linewidth=2)
plot(upper,  "上轨", color=color.gray)
plot(lower,  "下轨", color=color.gray)

// ═══════════════════════════════════════════════════════════════════
// 🎯 趋势状态
// ══════════════════════════════════════════════════════════════════
var int trend = 0 // -1=下降, 0=震荡, 1=上升

//trendUpBreak   = ta.crossover(close, upper)
// //trendDownBreak = ta.crossunder(close, lower)
trendUpBreak = close > upper and close[1] <= upper
trendDownBreak = close < lower and close[1] >= lower


// —— 修复点开始 —— //
prevTrend = trend
trend := close > upper ? 1 : close < lower ? -1 : 0
// —— 修复点结束 —— //


// ═══════════════════════════════════════════════════════════════════
// 📐 MACD
// ═══════════════════════════════════════════════════════════════════
// [macdLine, signalLine, hist] = ta.macd(close, 12, 26, 9)

// // 正负角线
// positiveBar = close > close[1] and macdLine > macdLine[1]
// negativeBar = close < close[1] and macdLine < macdLine[1]

// ═══════════════════════════════════════════════════════════════════
// 🔽 底部钝化与结构
// ═══════════════════════════════════════════════════════════════════
// twoNegBars   = negativeBar and negativeBar[1]
// priceNewLow  = low  < ta.lowest(low[1],  lookback)
// difNotNewLow = macdLine > ta.lowest(macdLine[1], lookback)
// bottomDull   = priceNewLow and difNotNewLow and twoNegBars

// var bool bottomDullActive = false
// if bottomDull
//     bottomDullActive := true

// bottomStruct = bottomDullActive and macdLine > macdLine[1] and macdLine[1] <= macdLine[2]
// if bottomStruct
//     bottomDullActive := false

// ══════════════════════════════════════════════════════════════════
// 🔼 顶部钝化与结构
// ═══════════════════════════════════════════════════════════════════
// twoPosBars   = positiveBar and positiveBar[1]
// priceNewHigh = high > ta.highest(high[1], lookback)
// difNotNewHigh= macdLine < ta.highest(macdLine[1], lookback)
// topDull      = priceNewHigh and difNotNewHigh and twoPosBars

// var bool topDullActive = false
// if topDull
//     topDullActive := true

// topStruct = topDullActive and macdLine < macdLine[1] and macdLine[1] >= macdLine[2]
// if topStruct
//     topDullActive := false

// ═══════════════════════════════════════════════════════════════════
// ⚠️ 纠错机制
// ══════════════════════════════════════════════════════════════════
// var float bottomRefDif = na
// var float topRefDif    = na

// if bottomStruct
//     bottomRefDif := macdLine[1]
// if topStruct
//     topRefDif    := macdLine[1]

// bottomCorrection = not na(bottomRefDif) and macdLine < bottomRefDif and macdLine[1] <= bottomRefDif[1] ? false : (not na(bottomRefDif) and macdLine < bottomRefDif and macdLine[1] >= bottomRefDif)
// topCorrection    = not na(topRefDif)    and macdLine > topRefDif    and macdLine[1] >= topRefDif[1]    ? false : (not na(topRefDif)    and macdLine > topRefDif    and macdLine[1] <= topRefDif)

// ═══════════════════════════════════════════════════════════════════
// 🧩 L4 特殊情况占位（最小改动）：
//   当趋势刚触且出现钝化（“结构触发概率大”）时，临时以“钝化消失”为准：先不执行趋势动作。
//   ——仅作为开关，不改变你原有结构/纠错实现。*/
// ═══════════════════════════════════════════════════════════════════
// specialHoldUp   = enableL4 and trendUpBreak   and (topDullActive   or topStruct)
// specialHoldDown = enableL4 and trendDownBreak and (bottomDullActive or bottomStruct)

// ═══════════════════════════════════════════════════════════════════
// 📊 策略执行（按等级开关）
// ═══════════════════════════════════════════════════════════════════

// if trendUpBreak and strategy.position_size == 0
//     strategy.entry("Long", strategy.long, comment="趋势上 100%")

// if trendDownBreak and strategy.position_size > 0
//     strategy.close_all(comment="趋势下 清仓")
isFlat = (strategy.position_size == 0) and (strategy.opentrades == 0)
plotchar(prevTrend==0 and trend==1, title="0→1", char='▲', location=location.abovebar, size=size.tiny)
plotchar(isFlat, "空仓确认", 'F', location=location.top, size=size.tiny)
plotchar(prevTrend==1 and trend==0, title="1→0", char='▼', location=location.belowbar, size=size.tiny)

if level == 0
    //  趋势上，满仓
    if trend == 1 and strategy.position_size == 0
        strategy.entry("Long", strategy.long, comment="->上\n +100%")
    // 趋势下，清仓
    if trend == -1 and strategy.position_size > 0
        strategy.close_all(comment="->下\n -100%")

if level == 1
    if  prevTrend != trend
        // 震荡转上涨,满仓
        if prevTrend == 0 and trend == 1 and strategy.position_size == 0
            strategy.entry("Long", strategy.long, comment="震->上\n +100%")
        // 震荡转📉，清仓
        if prevTrend == 0 and trend == -1 and strategy.position_size > 0
            strategy.close_all(comment="震->下\n -100%")

        // 📈转震荡，清仓
        if prevTrend == 1 and trend == 0 and strategy.position_size > 0
            strategy.close_all(comment="上->震\n -100%")
        // 📈转📉，清仓
        if prevTrend == 1 and trend == -1 and strategy.position_size > 0
            strategy.close_all(comment="上->下\n -100%")

        //下跌转震荡，清仓
        if prevTrend == -1 and trend == 0 and strategy.position_size > 0
            strategy.close_all(comment="下->震\n -100%")

        //下跌转上涨，满仓
        if prevTrend == -1 and trend == 1 and strategy.position_size == 0
            strategy.entry("Long", strategy.long, comment="下->上\n +100%")

// // [L1] 趋势突破上轨 → 满仓100%
// if level >= 1 and trendUpBreak and (not enableL4 or not specialHoldUp)
//     strategy.entry("Long", strategy.long, comment="趋势上 100%")

// // [L1] 趋势跌破下轨 → 清仓
// if level >= 1 and trendDownBreak and (not enableL4 or not specialHoldDown)
//     strategy.close_all(comment="趋势下 清仓")

// // [L2] 上升趋势中出现顶部结构 → 减仓40%（从100%减到60%）
// if enableL2 and topStruct and trend == 1 and strategy.position_size > 0
//     strategy.close("Long", qty_percent=40, comment="顶部结构 减仓40%")

// // [L2] 下降趋势中出现底部结构 → 加仓40%（从0%加到40%）
// if enableL2 and bottomStruct and trend == -1
//     if strategy.position_size == 0
//         qty = strategy.equity / close * 0.4    // 保留你原写法：后续我们再统一为“目标调仓”方式
//         strategy.entry("Long_bottom_struct", strategy.long, qty=qty, comment="底部结构 加40%")

// // [L3] 上升趋势中顶部纠错 → 目标再平衡到 100%
// if enableL3 and topCorrection and trend == 1 and strategy.position_size > 0
//     qty = (strategy.equity - strategy.position_size*close)/close
//     if qty > 0
//         strategy.entry("Long_rebal", strategy.long, qty=qty, comment="顶纠错 再平衡至100%")

// // [L3] 下降趋势中底部纠错 → 清仓
// if enableL3 and bottomCorrection and trend == -1
//     strategy.close_all(comment="底纠错 清仓")

// ═══════════════════════════════════════════════════════════════════
// 🎨 可视化
// ═══════════════════════════════════════════════════════════════════
plotshape(trendUpBreak,   "趋势上", shape.triangleup,   location.belowbar, color.green, size=size.normal,  text="上")
plotshape(trendDownBreak, "趋势下", shape.triangledown, location.abovebar, color.red,   size=size.normal,  text="下")
// plotshape(bottomStruct,   "底部结构", shape.circle,     location.belowbar, color.blue,  size=size.small,   text="底部")
// plotshape(topStruct,      "顶部结构", shape.circle,     location.abovebar, color.purple,size=size.small,   text="顶部")
// plotshape(bottomCorrection,"底纠错",  shape.xcross,     location.belowbar, color.orange,size=size.tiny,   text="底纠错")
// plotshape(topCorrection,   "顶纠错",  shape.xcross,     location.abovebar, color.orange,size=size.tiny,   text="顶纠错")

bgcolor(trend == 1 ? color.new(color.green, 95) : trend == -1 ? color.new(color.red, 95) : na)

