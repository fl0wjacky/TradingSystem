//@version=6
indicator("老猫3.0 - 严格隔峰版 + 扎实V反", overlay=true, max_labels_count=500, max_boxes_count=100, max_lines_count=100)

// ═══════════════════════════════════════════════════════════════════
// 📊 参数
// ═══════════════════════════════════════════════════════════════════
emaLength   = input.int(37,   "趋势EMA周期", minval=1, group="趋势通道")
atrLength   = input.int(20,   "通道ATR周期", minval=1, group="趋势通道")
atrMult     = input.float(0.47, "通道ATR倍数", step=0.01, minval=0, group="趋势通道")

confirmMode = input.string("DIF拐头", "结构确认强度", options=["DIF拐头", "拐头+柱转负"], group="结构引擎")

vfanEnable  = input.bool(true,  "启用扎实V反识别", group="V反")
volRatioMin = input.float(1.0,  "量比下限", step=0.1, group="V反")
distMinPct  = input.float(0.5,  "扎实带下限%(与1×ATR取大)", step=0.1, group="V反")
distMaxPct  = input.float(5.0,  "扎实带上限%", step=0.1, group="V反")
atrLenV     = input.int(14,     "V反ATR周期", group="V反")
allowSameBar= input.bool(true,  "允许单K压缩式(收位需≥0.7)", group="V反")
minWaveBars = input.int(1, "微波过滤:波存活N根才登记前峰/谷(1=关闭)", minval=1, maxval=5, group="结构引擎")
showPanel   = input.bool(false, "显示右上角信息面板", group="显示")
showPosLbl  = input.bool(false, "显示趋势/结构文字标签", group="显示")
showAllSigs = input.bool(false, "同一窗口显示全部关键K(默认仅第一个)", group="显示")
riskPct     = input.float(5.0, "头仓风险预算%(用于杠杆提示)", step=0.5, group="V反")
levCap      = input.int(3, "总杠杆帽(用于杠杆提示)", minval=1, group="V反")
useConfirmed= input.bool(false, "仅收盘确认后触发(防盘中闪烁)", group="结构引擎")
maxBaseBars = input.int(12, "V反窗口最长保鲜根数(筑底期)", minval=3, maxval=40, group="V反")
debugMode   = input.bool(false, "诊断模式:标注候选K的落选原因", group="V反")

// ═══════════════════════════════════════════════════════════════════
// 趋势通道(与2.0一致)
// ═══════════════════════════════════════════════════════════════════
emaMid = ta.ema(close, emaLength)
atrVal = ta.atr(atrLength)
upper  = emaMid + atrMult * atrVal
lower  = emaMid - atrMult * atrVal
plot(emaMid, "中轨", color=color.orange, linewidth=2)
plot(upper, "上轨", color=color.gray, linewidth=1)
plot(lower, "下轨", color=color.gray, linewidth=1)

var int trend = 0
trendUpBreak   = close > upper and close[1] <= upper[1]
trendDownBreak = close < lower and close[1] >= lower[1]
if close > upper
    trend := 1
else if close < lower
    trend := -1

// ═══════════════════════════════════════════════════════════════════
// 📐 MACD 与"波"的登记 —— 隔峰的本义
// 波 = 柱同号的连续段。前峰/前谷 = 上一个同向波完结时的 DIF 极值。
// 这是与2.0的根本区别:2.0用滚动20窗口近似隔峰,窗口会漂移;波不会。
// ═══════════════════════════════════════════════════════════════════
[macdLine, signalLine, hist] = ta.macd(close, 12, 26, 9)
positiveBar = close > close[1] and macdLine > macdLine[1]
negativeBar = close < close[1] and macdLine < macdLine[1]
twoPosBars  = positiveBar and positiveBar[1]
twoNegBars  = negativeBar and negativeBar[1]

histPos    = hist > 0
newPosWave = histPos and not histPos[1]
newNegWave = (not histPos) and histPos[1]

// 当前波累计极值
var float curPosWaveDifMax = na
var float curPosWaveHigh   = na
var float curNegWaveDifMin = na
var float curNegWaveLow    = na
// 上一完结波的极值(=隔峰比较基准)
var float prevPosWaveDifPeak = na
var float prevPosWaveHigh    = na
var float prevNegWaveDifTrough = na
var float prevNegWaveLow       = na

var float pendPeak = na
var float pendHigh = na
var float pendTrough = na
var float pendLow  = na
var int   posLen = 0
var int   negLen = 0
var float shadowNmin = na
var float shadowNlow = na
var float shadowPmax = na
var float shadowPhigh = na

if newNegWave                       // 正波刚完结 → 前峰进入待确认区
    pendPeak := curPosWaveDifMax
    pendHigh := curPosWaveHigh
    shadowPmax := curPosWaveDifMax
    shadowPhigh := curPosWaveHigh
    curNegWaveDifMin := not na(pendTrough) ? math.min(pendTrough, macdLine) : macdLine   // 上一正波若是未确认微波 → 负波延续,极值合并
    curNegWaveLow    := not na(pendTrough) ? math.min(pendLow, low)         : low
    if not na(pendTrough)
        pendTrough := na
    negLen := 0
if newPosWave                       // 负波刚完结 → 前谷进入待确认区
    pendTrough := curNegWaveDifMin
    pendLow    := curNegWaveLow
    shadowNmin := curNegWaveDifMin
    shadowNlow := curNegWaveLow
    curPosWaveDifMax := not na(pendPeak) ? math.max(pendPeak, macdLine) : macdLine       // 上一负波若是未确认微波 → 正波延续,极值合并
    curPosWaveHigh   := not na(pendPeak) ? math.max(pendHigh, high)     : high
    if not na(pendPeak)
        pendPeak := na
    posLen := 0
if histPos
    posLen += 1
    if posLen >= minWaveBars and not na(pendTrough)   // 新正波存活达标 → 确认登记前谷
        prevNegWaveDifTrough := pendTrough
        prevNegWaveLow       := pendLow
        pendTrough := na
    curPosWaveDifMax := na(curPosWaveDifMax) ? macdLine : math.max(curPosWaveDifMax, macdLine)
    curPosWaveHigh   := na(curPosWaveHigh)   ? high     : math.max(curPosWaveHigh, high)
else
    negLen += 1
    if negLen >= minWaveBars and not na(pendPeak)     // 新负波存活达标 → 确认登记前峰
        prevPosWaveDifPeak := pendPeak
        prevPosWaveHigh    := pendHigh
        pendPeak := na
    curNegWaveDifMin := na(curNegWaveDifMin) ? macdLine : math.min(curNegWaveDifMin, macdLine)
    curNegWaveLow    := na(curNegWaveLow)    ? low      : math.min(curNegWaveLow, low)

// ═══════════════════════════════════════════════════════════════════
// 🔼 顶部:钝化 → 结构 → 纠错(严格版)
// 钝化   = 本波价格越过前波高点,而 DIF 仍低于前峰(正角线过滤)
// 结构   = 钝化活跃时 DIF 拐头(可选加严:柱转负)
// 钝化消失 = DIF 上破【前峰】——唯一标准,不用局部峰
//            结构已执行 → 纠错(加回);未执行 → 静默撤销
// 复位   = 纠错/撤销后清空基准;同一波再满足钝化条件可重新武装
// ═══════════════════════════════════════════════════════════════════
var bool  topDullActive = false
var bool  topStructDone = false
var float topPeakRef    = na
var bool  topReduced    = false
var bool  botAdded      = false
var bool  tempMode      = false

topDullCond = histPos and not na(prevPosWaveDifPeak) and high > prevPosWaveHigh and macdLine < prevPosWaveDifPeak and twoPosBars
canFire = not useConfirmed or barstate.isconfirmed
topDullNew  = canFire and topDullCond and not topDullActive and not topStructDone
if topDullNew
    topDullActive := true
    topPeakRef    := prevPosWaveDifPeak

difTurnDown = macdLine < macdLine[1] and macdLine[1] >= macdLine[2]
topConfirm  = confirmMode == "DIF拐头" ? difTurnDown : (difTurnDown or (hist < 0 and hist[1] >= 0))
topStructRaw = canFire and topDullActive and topConfirm
topStruct    = topStructRaw and not tempMode          // 临时模式中: 状态推进,操作暂停(Lv4)
if topStructRaw
    topDullActive := false
    topStructDone := true

topVanish = canFire and not na(topPeakRef) and macdLine > topPeakRef and macdLine[1] <= topPeakRef
topCorrection = topVanish and topStructDone           // 钝化消失且已减仓 → 加回
topSilentCancel = topVanish and topDullActive          // 未减仓 → 静默撤销
if topVanish
    topDullActive := false
    topStructDone := false
    topPeakRef    := na

// ═══════════════════════════════════════════════════════════════════
// 🔽 底部:完全镜像
// ═══════════════════════════════════════════════════════════════════
var bool  botDullActive = false
var bool  botStructDone = false
var float botTroughRef  = na

botDullCond = (not histPos) and not na(prevNegWaveDifTrough) and low < prevNegWaveLow and macdLine > prevNegWaveDifTrough and twoNegBars
botDullNew  = canFire and botDullCond and not botDullActive and not botStructDone
if botDullNew
    botDullActive := true
    botTroughRef  := prevNegWaveDifTrough

difTurnUp  = macdLine > macdLine[1] and macdLine[1] <= macdLine[2]
botConfirm = confirmMode == "DIF拐头" ? difTurnUp : (difTurnUp or (hist > 0 and hist[1] <= 0))
botStructRaw = canFire and botDullActive and botConfirm
botStruct    = botStructRaw and not tempMode
if botStructRaw
    botDullActive := false
    botStructDone := true

botVanish = canFire and not na(botTroughRef) and macdLine < botTroughRef and macdLine[1] >= botTroughRef
botCorrection = botVanish and botStructDone
botSilentCancel = botVanish and botDullActive
if botVanish
    botDullActive := false
    botStructDone := false
    botTroughRef  := na

// 趋势翻转时结构状态整体复位(换战场)
if trendUpBreak or trendDownBreak
    topDullActive := false
    topStructDone := false
    topPeakRef := na
    botDullActive := false
    botStructDone := false
    botTroughRef := na
    topReduced := false
    botAdded := false

plotshape(topDullNew, "顶部钝化", shape.circle, location.abovebar, color.purple, size=size.tiny)
plotshape(topStruct, "顶部结构", shape.triangledown, location.abovebar, color.red, size=size.small)
plotshape(topStructRaw and tempMode, "顶部结构(临时模式暂停)", shape.triangledown, location.abovebar, color.new(color.red,60), size=size.tiny)
plotshape(botDullNew, "底部钝化", shape.circle, location.belowbar, color.blue, size=size.tiny)
plotshape(botStruct, "底部结构", shape.triangleup, location.belowbar, color.green, size=size.small)
plotshape(botStructRaw and tempMode, "底部结构(临时模式暂停)", shape.triangleup, location.belowbar, color.new(color.green,60), size=size.tiny)

// ═══════════════════════════════════════════════════════════════════
// 🔄 临时模式(趋势突破与钝化并存 → 暂停结构操作,以钝化消失为准)
// ═══════════════════════════════════════════════════════════════════
if (trendUpBreak or trendDownBreak) and (topDullActive or botDullActive)
    tempMode := true
if topVanish or botVanish or ((trendUpBreak or trendDownBreak) and not (topDullActive or botDullActive))
    tempMode := false
bgcolor(tempMode ? color.new(color.yellow, 90) : na, title="临时模式")

// ═══════════════════════════════════════════════════════════════════
// 💰 仓位(与2.0规则一致; 纠错仅在结构真实执行过时反向操作)
// ═══════════════════════════════════════════════════════════════════
var float position = 0.0
if trendUpBreak
    position := 60.0
else if trendDownBreak
    position := 0.0
else if not tempMode
    if topStruct and trend == 1
        position := 40.0
        topReduced := true
    else if botStruct and trend == -1
        position := 40.0
        botAdded := true
    else if topCorrection and trend == 1 and topReduced
        position := 60.0
        topReduced := false
    else if botCorrection and trend == -1 and botAdded
        position := 0.0
        botAdded := false

var float lastPosition = 0.0
if showPosLbl and position != lastPosition
    change = position - lastPosition
    labelText = ""
    if trendUpBreak
        labelText := tempMode ? "趋势为上\n仓位60%(钝化中)" : "趋势为上\n仓位60%"
    else if trendDownBreak
        labelText := tempMode ? "趋势为下\n清仓(钝化中)" : "趋势为下\n清仓"
    else if botStruct
        labelText := "底部结构\n加仓至40%"
    else if topStruct
        labelText := "顶部结构\n减仓至40%"
    else if botCorrection
        labelText := "底部纠错(DIF跌破前谷)\n清仓"
    else if topCorrection
        labelText := "顶部纠错(DIF上破前峰)\n恢复60%"
    else
        labelText := (change > 0 ? "+" : "") + str.tostring(change, "#") + "%"
    labelColor = change > 0 ? color.new(color.green, 0) : change < 0 ? color.new(color.red, 0) : color.new(color.gray, 0)
    labelStyle = change > 0 ? label.style_label_up : change < 0 ? label.style_label_down : label.style_label_center
    yPos = change > 0 ? low * 0.985 : change < 0 ? high * 1.015 : close
    label.new(bar_index, yPos, text=labelText, color=labelColor, textcolor=color.white, style=labelStyle, size=size.normal)
lastPosition := position

// 静默撤销的提示(未减仓时钝化消失,只标记不动仓)
plotshape(topSilentCancel, "顶钝化撤销", shape.xcross, location.abovebar, color.gray, size=size.tiny)
plotshape(botSilentCancel, "底钝化撤销", shape.xcross, location.belowbar, color.gray, size=size.tiny)

// ═══════════════════════════════════════════════════════════════════
// 🟡 扎实V反识别 + 合格入场带
// 摆动低点 = 近7根最低(因果,不偷看未来)
// 反弹K   = 阳线 + 收位达标 + 量比达标,低点后0~3根内
// 扎实带  = 低点上方 [max(0.5%, 1×ATR) , 5%],黄色区
// 单K压缩式:低点自身即带量阳线,收位需≥0.7(第二章实证:扫损率更高)
// ═══════════════════════════════════════════════════════════════════
atrV  = ta.atr(atrLenV)
volMa = ta.sma(volume, 20)

var float vLow    = na
var int   vLowOrigin = na
var float vBandTop = na
var int   shownOrigin = -1
var bool  vAlive  = false
var string vDeadReason = na
var box   vBox  = na
var line  vLine = na

swingLow = low == ta.lowest(low, 7)
if vfanEnable and swingLow
    vLow    := low
    vLowOrigin := bar_index
    vAlive  := true
    vDeadReason := na
    // 画/更新合格入场带(黄色)与止损线
    bandBot = vLow * (1 + math.max(distMinPct / 100, atrV / vLow))
    bandTop = vLow * (1 + distMaxPct / 100)
    if not na(vBox)
        box.delete(vBox)
    if not na(vLine)
        line.delete(vLine)
    boxTxt = "V反合格入场带 " + str.tostring(bandBot, format.mintick) + " ~ " + str.tostring(bandTop, format.mintick) + "\n带量阳线收于带内 = 合格头仓 · 止损 " + str.tostring(vLow, format.mintick)
    vBandTop := bandTop
    vBox  := box.new(bar_index, bandTop, bar_index + maxBaseBars, bandBot, bgcolor=color.new(color.yellow, 82), border_color=color.new(color.orange, 55), text=boxTxt, text_color=color.new(color.orange, 10), text_size=size.tiny, text_halign=text.align_left, text_valign=text.align_top)
    vLine := line.new(bar_index, vLow, bar_index + maxBaseBars, vLow, color=color.red, style=line.style_dashed, width=1)

// 窗口保鲜(状态制): 收盘跌破止损或收出带顶 → 失效; 超过保鲜上限 → 失效
if vAlive and close < vLow
    vAlive := false
    vDeadReason := "收盘破止损@" + str.tostring(bar_index)
if vAlive and not na(vBandTop) and close > vBandTop and close[1] > vBandTop
    vAlive := false
    vDeadReason := "连续收出带顶"
barsSince = na(vLowOrigin) ? 999 : bar_index - vLowOrigin
if vAlive and barsSince > maxBaseBars
    vAlive := false
    vDeadReason := "超过保鲜上限" + str.tostring(maxBaseBars) + "根"
posInRange = (high - low) > 0 ? (close - low) / (high - low) : 0.0
posReq  = bar_index == vLowOrigin ? 0.7 : 0.5   // 0.7只适用于打出低点的那根K本身;回踩重置不改分类
minBars = allowSameBar ? 0 : 1
distPct = na(vLow) ? na : (close - vLow) / close * 100
minDist = math.max(distMinPct, atrV / close * 100)

reboundOK = close > open and posInRange >= posReq and volMa > 0 and volume >= volRatioMin * volMa
vfanSignal = canFire and vfanEnable and not na(vLow) and vAlive and barsSince >= minBars and reboundOK and low >= vLow and distPct >= minDist and distPct <= distMaxPct

// 诊断(全量播报): 窗口内每根阳线都打出全部读数;沉默 = 这根K不是阳线或不在窗口
if debugMode and vfanEnable and not na(vLow) and close > open and not vfanSignal
    okPos  = posInRange >= posReq
    okVol  = volMa > 0 and volume >= volRatioMin * volMa
    okDmin = not na(distPct) and distPct >= minDist
    okDmax = not na(distPct) and distPct <= distMaxPct
    okLow  = low >= vLow
    txt = "收位" + str.tostring(posInRange, "#.##") + (okPos ? "" : "✗req" + str.tostring(posReq, "#.#"))
    txt += " 量" + str.tostring(volMa > 0 ? volume / volMa : 0, "#.##") + (okVol ? "" : "✗")
    txt += " 距" + str.tostring(distPct, "#.##") + "%" + (okDmin ? "" : "✗<" + str.tostring(minDist, "#.##")) + (okDmax ? "" : "✗>5")
    txt += " 第" + str.tostring(barsSince) + "根"
    if not vAlive
        txt += " 失效[" + (na(vDeadReason) ? "?" : vDeadReason) + "]"
    if not okLow
        txt += " 破低"
    if not canFire
        txt += " 等收盘"
    label.new(bar_index, high * 1.003, text=txt, color=color.new(color.gray, 35), textcolor=color.white, style=label.style_label_down, size=size.tiny)

vfanShow = vfanSignal and (showAllSigs or vLowOrigin != shownOrigin)

// 合格但被"仅显示第一个"隐藏的K,诊断模式下留痕
if debugMode and vfanSignal and not vfanShow
    label.new(bar_index, high * 1.003, text="合格·窗口第" + str.tostring(barsSince) + "根·默认隐藏", color=color.new(color.orange, 60), textcolor=color.white, style=label.style_label_down, size=size.tiny)

if vfanShow
    shownOrigin := vLowOrigin
    tag = (barsSince == 0 ? "V反✓(单K压缩式)" : "V反✓") + " · 窗口第" + str.tostring(barsSince) + "根"
    levHint = math.max(1, math.min(math.floor(riskPct / distPct), levCap))
    label.new(bar_index, high * 1.005,
         text=tag + "\n收盘 " + str.tostring(close, format.mintick) + " · 收位 " + str.tostring(posInRange, "#.##") + "\n止损 " + str.tostring(vLow, format.mintick) + " · 距离 " + str.tostring(distPct, "#.##") + "%\n量比 " + str.tostring(volume / volMa, "#.##") + " · 可开杠杆 " + str.tostring(levHint) + "x",
         color=color.new(color.orange, 0), textcolor=color.white, style=label.style_label_down, size=size.small)

alertcondition(vfanShow, title="扎实V反", message="{{ticker}} 出现扎实带量V反,请查看图表")
alertcondition(position != position[1], title="仓位变动", message="{{ticker}} 仓位发生变动,请查看图表")

// ═══════════════════════════════════════════════════════════════════
// 🎨 通道填充 + 信息面板
// ═══════════════════════════════════════════════════════════════════
p1 = plot(upper, display=display.none)
p2 = plot(lower, display=display.none)
bgColor = trend == 1 ? color.new(color.green, 92) : trend == -1 ? color.new(color.red, 92) : color.new(color.gray, 95)
fill(p1, p2, color=bgColor, title="趋势背景")

var table infoTable = showPanel ? table.new(position=position.top_right, columns=2, rows=6, bgcolor=color.new(color.black, 85), frame_color=color.gray, frame_width=1) : na
if showPanel and barstate.islast
    table.cell(infoTable, 0, 0, "当前仓位", text_color=color.white, bgcolor=color.new(color.blue, 50))
    table.cell(infoTable, 1, 0, str.tostring(position, "#") + "%", text_color=color.white, bgcolor=color.new(color.blue, 50))
    table.cell(infoTable, 0, 1, "趋势状态", text_color=color.white)
    trendText = trend == 1 ? "上升" : trend == -1 ? "下降" : "震荡"
    trendColor = trend == 1 ? color.green : trend == -1 ? color.red : color.gray
    table.cell(infoTable, 1, 1, trendText, text_color=trendColor)
    table.cell(infoTable, 0, 2, "结构状态", text_color=color.white)
    stText = topDullActive ? "顶钝化中" : botDullActive ? "底钝化中" : topStructDone ? "顶结构已执行" : botStructDone ? "底结构已执行" : "无"
    table.cell(infoTable, 1, 2, stText, text_color=color.yellow)
    table.cell(infoTable, 0, 3, "前峰/前谷", text_color=color.white)
    refText = not na(topPeakRef) ? "峰 " + str.tostring(topPeakRef, "#") : not na(botTroughRef) ? "谷 " + str.tostring(botTroughRef, "#") : "—"
    table.cell(infoTable, 1, 3, refText, text_color=color.white)
    table.cell(infoTable, 0, 4, "MACD", text_color=color.white)
    table.cell(infoTable, 1, 4, macdLine > 0 ? "多头" : "空头", text_color=macdLine > 0 ? color.green : color.red)
    table.cell(infoTable, 0, 5, "V反窗口", text_color=color.white)
    vwTxt = na(vLow) ? "无" : vAlive ? "保鲜中·第" + str.tostring(barsSince) + "根·止损" + str.tostring(vLow, format.mintick) : "失效[" + (na(vDeadReason) ? "?" : vDeadReason) + "]"
    table.cell(infoTable, 1, 5, vwTxt, text_color=vAlive ? color.yellow : color.gray)
