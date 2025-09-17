# 策略配置指南

## 概述

炒币的猫交易系统支持多种交易策略，可以通过配置文件或 API 进行策略管理。

## 内置策略

### 1. 网格交易策略 (Grid Trading)

在设定的价格区间内自动低买高卖。

**配置参数：**
```yaml
strategy:
  type: grid
  symbol: BTCUSDT
  parameters:
    upper_price: 52000      # 网格上限
    lower_price: 48000      # 网格下限
    grid_count: 20          # 网格数量
    investment: 10000       # 投资金额
    stop_loss: 45000        # 止损价格
    take_profit: 55000      # 止盈价格
```

**适用场景：**
- 震荡行情
- 区间交易
- 被动收益

### 2. 均线策略 (Moving Average)

基于移动平均线的趋势跟踪策略。

**配置参数：**
```yaml
strategy:
  type: ma_cross
  symbol: BTCUSDT
  timeframe: 1h
  parameters:
    fast_period: 7          # 快线周期
    slow_period: 25         # 慢线周期
    volume_filter: true     # 成交量过滤
    position_size: 0.1      # 仓位大小
```

**信号规则：**
- 金叉买入：快线上穿慢线
- 死叉卖出：快线下穿慢线

### 3. RSI 策略

基于相对强弱指标的超买超卖策略。

**配置参数：**
```yaml
strategy:
  type: rsi
  symbol: BTCUSDT
  timeframe: 15m
  parameters:
    period: 14              # RSI周期
    oversold: 30            # 超卖阈值
    overbought: 70          # 超买阈值
    position_size: 0.1      # 仓位大小
```

### 4. 马丁格尔策略 (Martingale)

逐步加仓的网格策略变种。

**配置参数：**
```yaml
strategy:
  type: martingale
  symbol: BTCUSDT
  parameters:
    initial_amount: 100     # 初始金额
    multiplier: 2           # 加仓倍数
    max_rounds: 5           # 最大加仓次数
    price_gap: 0.01         # 价格间隔
    take_profit: 0.02       # 止盈比例
```

⚠️ **风险警告**：马丁格尔策略风险较高，请谨慎使用。

### 5. 三角套利 (Triangular Arbitrage)

利用三个交易对之间的价差进行套利。

**配置参数：**
```yaml
strategy:
  type: triangular_arbitrage
  parameters:
    base_currency: USDT
    min_profit: 0.001       # 最小利润率
    max_amount: 1000        # 最大交易金额
    exchanges:
      - binance
      - okx
```

## 自定义策略

### 策略基类

```python
from cbdcat.strategy import BaseStrategy

class MyStrategy(BaseStrategy):
    def __init__(self, config):
        super().__init__(config)
        self.setup_indicators()
    
    def on_tick(self, data):
        """处理每个价格变动"""
        signal = self.generate_signal(data)
        if signal == 'BUY':
            self.buy(data['price'])
        elif signal == 'SELL':
            self.sell(data['price'])
    
    def generate_signal(self, data):
        """生成交易信号"""
        # 实现你的策略逻辑
        pass
```

### 注册策略

```python
from cbdcat import StrategyManager

manager = StrategyManager()
manager.register('my_strategy', MyStrategy)
manager.run('my_strategy', config)
```

## 回测配置

### 回测参数

```yaml
backtest:
  start_date: '2023-01-01'
  end_date: '2023-12-31'
  initial_capital: 10000
  commission: 0.001         # 手续费率
  slippage: 0.001          # 滑点
  data_frequency: '1m'      # 数据频率
```

### 运行回测

```bash
python -m cbdcat.backtest --config backtest.yaml --strategy grid
```

## 风控参数

### 全局风控

```yaml
risk_control:
  max_drawdown: 0.2         # 最大回撤
  max_position: 0.3         # 最大仓位
  daily_loss_limit: 0.05    # 日亏损限制
  correlation_limit: 0.7    # 相关性限制
```

### 策略级风控

```yaml
strategy:
  risk_params:
    stop_loss: 0.02         # 止损比例
    take_profit: 0.05       # 止盈比例
    trailing_stop: 0.01     # 移动止损
    max_orders: 10          # 最大订单数
```

## 性能优化

### 1. 数据缓存

```yaml
cache:
  enabled: true
  type: redis
  ttl: 3600                 # 缓存时间（秒）
```

### 2. 并行处理

```yaml
execution:
  parallel: true
  workers: 4                # 工作进程数
  batch_size: 100          # 批处理大小
```

### 3. 策略调度

```yaml
scheduler:
  type: cron
  rules:
    - strategy: grid
      schedule: '*/5 * * * *'  # 每5分钟
    - strategy: ma_cross
      schedule: '0 * * * *'    # 每小时
```

## 监控指标

### 关键指标

- **收益率** (Return Rate)
- **夏普比率** (Sharpe Ratio)
- **最大回撤** (Max Drawdown)
- **胜率** (Win Rate)
- **盈亏比** (Profit/Loss Ratio)

### 监控配置

```yaml
monitoring:
  metrics:
    - return_rate
    - sharpe_ratio
    - max_drawdown
    - win_rate
  alerts:
    - type: drawdown
      threshold: 0.1
      action: stop_strategy
    - type: daily_loss
      threshold: 0.05
      action: notify
```

## 最佳实践

1. **小额测试**：新策略先用小额资金测试
2. **分散投资**：不要把所有资金放在一个策略
3. **定期复盘**：定期分析策略表现并优化
4. **风控第一**：始终设置止损，控制风险
5. **避免过拟合**：回测优秀不代表实盘表现好

## 常见问题

### Q: 策略不执行怎么办？

检查以下项目：
1. API 连接是否正常
2. 账户余额是否充足
3. 策略参数是否正确
4. 查看日志文件排查错误

### Q: 如何优化策略参数？

使用参数优化工具：
```bash
python -m cbdcat.optimize --strategy grid --method grid_search
```

### Q: 多个策略冲突怎么处理？

设置策略优先级和互斥规则：
```yaml
strategy_rules:
  priority:
    - high_frequency
    - grid
    - ma_cross
  mutex:
    - [grid, martingale]    # 不能同时运行
```