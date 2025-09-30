//@version=6
indicator("老猫2.0系统 - 趋势+结构+仓位+纠错（实战还原版）", overlay=true, max_labels_count=500)

// ———————— 用户参数（来自直播反推） ————————
emaLength = input.int(37, "趋势中轨EMA")
atrLength = input.int(20, "ATR周期")
atrMult = input.float(0.47, "ATR倍数", step=0.01)

// ———————— 趋势通道 ————————
emaMid = ta.ema(close, emaLength)
atrVal = ta.atr(atrLength)
upper = emaMid + atrMult * atrVal
lower = emaMid - atrMult * atrVal

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

// ———————— MACD 结构识别 ————————
[macdLine, signalLine, _] = ta.macd(close, 12, 26, 9)
hist = macdLine - signalLine

pivotLow = ta.pivotlow(low, 5, 5)
pivotHigh = ta.pivothigh(high, 5, 5)

// ———————— 底部结构 ————————
prevLow = ta.valuewhen(not na(pivotLow), pivotLow, 1)
currLow = ta.valuewhen(not na(pivotLow), pivotLow, 0)
prevDifLow = ta.valuewhen(not na(pivotLow), macdLine, 1)
currDifLow = ta.valuewhen(not na(pivotLow), macdLine, 0)

isBottomDull = not na(currLow) and not na(prevLow) and currLow < prevLow and currDifLow > prevDifLow
isBottomStruct = isBottomDull and (macdLine > macdLine[1])

// ———————— 顶部结构 ————————
prevHigh = ta.valuewhen(not na(pivotHigh), pivotHigh, 1)
currHigh = ta.valuewhen(not na(pivotHigh), pivotHigh, 0)
prevDifHigh = ta.valuewhen(not na(pivotHigh), macdLine, 1)
currDifHigh = ta.valuewhen(not na(pivotHigh), macdLine, 0)

isTopDull = not na(currHigh) and not na(prevHigh) and currHigh > prevHigh and currDifHigh < prevDifHigh
isTopStruct = isTopDull and (macdLine < macdLine[1])

// ———————— 纠错逻辑 ————————
var float bottomFrontDif = na
if isBottomStruct
    bottomFrontDif := prevDifLow
isBottomCorrection = not na(bottomFrontDif) and macdLine < bottomFrontDif

var float topFrontDif = na
if isTopStruct
    topFrontDif := prevDifHigh
isTopCorrection = not na(topFrontDif) and macdLine > topFrontDif

// ———————— 特殊规则：临时切换标准（第九章第6段） ————————
var bool tempMode = false
// 趋势刚触发 + 出现钝化 → 进入临时模式
if (trendState != trendState[1]) and (isBottomDull or isTopDull)
    tempMode := true
// 结构形成或纠错 → 退出临时模式
if isBottomStruct or isTopStruct or isBottomCorrection or isTopCorrection
    tempMode := false

// ———————— 仓位计算（严格按第九章 + 特殊规则） ————————
calcPosition() =>
    pos = 0.0
    if trendState == 1
        pos := 60.0
        // 特殊规则：趋势上 + 临时模式 + 顶部纠错 → 保持60%
        if tempMode and isTopCorrection
            pos := 60.0
    else if trendState == -1
        if isBottomStruct
            pos := 40.0
        else if isBottomCorrection
            pos := 0.0
        // 特殊规则：趋势下 + 临时模式 + 底部纠错 → 清仓
        if tempMode and isBottomCorrection
            pos := 0.0
    pos

position = calcPosition()

// ———————— 通道填充 ————————
p1 = plot(upper, "上轨", color=color.gray, linewidth=1)
p2 = plot(lower, "下轨", color=color.gray, linewidth=1)
fill(p1, p2, color=trendState == 1 ? color.new(color.green, 90) : trendState == -1 ? color.new(color.red, 90) : na)

// ———————— 生成语义化标签文本（修正版） ————————
var float lastPos = na
if bar_index > 0
    change = position - lastPos
    if change != 0
        actionText = ""
        if tempMode
            // 明确提示：趋势刚触发 + 钝化 → 暂不操作，等待钝化消失
            if trendState == 1
                actionText := "趋势刚上+钝化：\n暂不加仓，\n等钝化消失"
            else
                actionText := "趋势刚下+钝化：\n暂不减仓，\n等钝化消失"
        else if trendState == 1 and change > 0
            actionText := "趋势为上\n+60%"
        else if trendState == -1 and position == 0
            actionText := "趋势为下\n清仓"
        else if isTopStruct
            actionText := "顶部结构\n-40%"
        else if isBottomStruct
            actionText := "底部结构\n+40%"
        else if isBottomCorrection
            actionText := "结构纠错\n-40%"
        else if isTopCorrection
            actionText := "结构纠错\n+40%"
        else
            actionText := (change > 0 ? "+" : "") + str.tostring(change, "#") + "%"

        if change > 0
            label.new(bar_index, low * 0.96, text=actionText, 
                     color=color.green, textcolor=color.white, style=label.style_label_up)
        else
            label.new(bar_index, high * 1.04, text=actionText, 
                     color=color.red, textcolor=color.white, style=label.style_label_down)
    lastPos := position

// ———————— 警报 ————————
positionChanged = not na(lastPos) and position != lastPos
alertcondition(positionChanged, title="【仓位变动】", message="【{{ticker}}】仓位变动，请查看日线图。")
