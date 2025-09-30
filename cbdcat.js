//@version=5
indicator("老猫2.0系统（实战还原版）", overlay=true, max_labels_count=500)

// ———————— 趋势通道（EMA37 ± 0.47×ATR20） ————————
emaMid = ta.ema(close, 37)
atrVal = ta.atr(20)
upper = emaMid + 0.47 * atrVal
lower = emaMid - 0.47 * atrVal

plot(emaMid, "趋势中轨", color=color.orange, linewidth=2)
plot(upper, "上轨", color=color.gray, linewidth=1)
plot(lower, "下轨", color=color.gray, linewidth=1)

// 趋势状态
trendUp = close > upper
trendDown = close < lower
var int trendState = 0
if trendUp
    trendState := 1
else if trendDown
    trendState := -1

// ———————— MACD 结构（简化钝化条件） ————————
[macdLine, signalLine, _] = ta.macd(close, 12, 26, 9)
hist = macdLine - signalLine

pivotLow = ta.pivotlow(low, 5, 5)
pivotHigh = ta.pivothigh(high, 5, 5)

// 全局记录
prevLow = ta.valuewhen(not na(pivotLow), pivotLow, 1)
currLow = ta.valuewhen(not na(pivotLow), pivotLow, 0)
prevDifLow = ta.valuewhen(not na(pivotLow), macdLine, 1)
currDifLow = ta.valuewhen(not na(pivotLow), macdLine, 0)

// 钝化：价格新低 + DIF 不新低（不再强制要求2根负脚线）
isBottomDull = not na(currLow) and not na(prevLow) and currLow < prevLow and currDifLow > prevDifLow
isBottomStruct = isBottomDull and (macdLine > macdLine[1])

// ———————— 纠错逻辑 ————————
var float bottomFrontDif = na
if isBottomStruct
    bottomFrontDif := prevDifLow
isBottomCorrection = not na(bottomFrontDif) and macdLine < bottomFrontDif

// ———————— 特殊规则：临时切换标准（第九章第6段） ————————
// 当趋势刚触发（trendState变化）且出现钝化 → 临时以钝化消失为准
var bool tempMode = false
if (trendState != trendState[1]) and isBottomDull
    tempMode := true
if isBottomStruct or isBottomCorrection
    tempMode := false

// ———————— 仓位计算 ————————
calcPosition() =>
    pos = 0.0
    if trendState == 1
        pos := 60.0
    else if trendState == -1
        if isBottomStruct
            pos := 40.0  // 简化：默认距离近
        else if isBottomCorrection
            pos := 0.0
    // 临时模式下，即使趋势上，也允许减仓
    if tempMode and isBottomCorrection
        pos := 0.0
    pos

position = calcPosition()

// ———————— 标记 ————————
var float lastPos = na
if bar_index > 0
    change = position - lastPos
    if change != 0
        if change > 0
            label.new(bar_index, low * 0.995, text="+" + str.tostring(change, "#") + "%", 
                     color=color.green, textcolor=color.white, style=label.style_label_up)
        else
            label.new(bar_index, high * 1.005, text=str.tostring(change, "#") + "%", 
                     color=color.red, textcolor=color.white, style=label.style_label_down)
lastPos := position

// ———————— 警报 ————————
positionChanged = not na(lastPos) and position != lastPos
alertcondition(positionChanged, title="【仓位变动】", message="仓位变动，请查看日线图。")
