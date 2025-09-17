# API 文档

## 概述

炒币的猫交易系统提供 RESTful API 和 WebSocket API，支持程序化交易和实时数据订阅。

## 认证

所有 API 请求需要使用 API Key 和 Secret 进行签名认证。

### 请求头

```
X-API-KEY: your_api_key
X-SIGNATURE: request_signature
X-TIMESTAMP: unix_timestamp
```

## REST API

### 基础信息

#### 获取服务器时间

```http
GET /api/v1/time
```

**响应示例：**
```json
{
  "serverTime": 1639476847000
}
```

### 账户相关

#### 获取账户信息

```http
GET /api/v1/account
```

**响应示例：**
```json
{
  "balances": [
    {
      "asset": "BTC",
      "free": "1.00000000",
      "locked": "0.00000000"
    },
    {
      "asset": "USDT",
      "free": "10000.00000000",
      "locked": "0.00000000"
    }
  ],
  "updateTime": 1639476847000
}
```

### 交易相关

#### 下单

```http
POST /api/v1/order
```

**请求参数：**
| 参数 | 类型 | 必须 | 描述 |
|------|------|------|------|
| symbol | string | 是 | 交易对 |
| side | string | 是 | BUY/SELL |
| type | string | 是 | LIMIT/MARKET |
| quantity | decimal | 是 | 数量 |
| price | decimal | 否 | 价格(限价单必须) |

**请求示例：**
```json
{
  "symbol": "BTCUSDT",
  "side": "BUY",
  "type": "LIMIT",
  "quantity": 0.001,
  "price": 50000
}
```

**响应示例：**
```json
{
  "orderId": "123456789",
  "symbol": "BTCUSDT",
  "status": "NEW",
  "clientOrderId": "my_order_001",
  "price": "50000.00",
  "avgPrice": "0.00",
  "origQty": "0.001",
  "executedQty": "0",
  "type": "LIMIT",
  "side": "BUY",
  "time": 1639476847000
}
```

#### 查询订单

```http
GET /api/v1/order/{orderId}
```

#### 取消订单

```http
DELETE /api/v1/order/{orderId}
```

### 市场数据

#### 获取K线数据

```http
GET /api/v1/klines
```

**请求参数：**
| 参数 | 类型 | 必须 | 描述 |
|------|------|------|------|
| symbol | string | 是 | 交易对 |
| interval | string | 是 | 时间间隔 |
| limit | int | 否 | 数量限制 |

#### 获取深度数据

```http
GET /api/v1/depth
```

**请求参数：**
| 参数 | 类型 | 必须 | 描述 |
|------|------|------|------|
| symbol | string | 是 | 交易对 |
| limit | int | 否 | 深度档位 |

## WebSocket API

### 连接

```
wss://api.cbdcat.com/ws
```

### 订阅

#### 订阅实时行情

```json
{
  "method": "SUBSCRIBE",
  "params": [
    "btcusdt@ticker"
  ],
  "id": 1
}
```

#### 订阅深度数据

```json
{
  "method": "SUBSCRIBE",
  "params": [
    "btcusdt@depth"
  ],
  "id": 2
}
```

### 数据推送格式

#### 行情数据

```json
{
  "e": "24hrTicker",
  "E": 1639476847000,
  "s": "BTCUSDT",
  "p": "1000.00",
  "P": "2.08",
  "w": "48500.00",
  "c": "49000.00",
  "Q": "0.001",
  "o": "48000.00",
  "h": "49500.00",
  "l": "47500.00",
  "v": "1234.567",
  "q": "59871234.56"
}
```

## 策略 API

### 创建策略

```http
POST /api/v1/strategy
```

**请求参数：**
```json
{
  "name": "网格交易策略",
  "type": "GRID",
  "symbol": "BTCUSDT",
  "parameters": {
    "upperPrice": 52000,
    "lowerPrice": 48000,
    "gridNum": 20,
    "investment": 10000
  }
}
```

### 启动/停止策略

```http
POST /api/v1/strategy/{strategyId}/start
POST /api/v1/strategy/{strategyId}/stop
```

## 错误代码

| 错误代码 | 描述 |
|----------|------|
| 1000 | 未知错误 |
| 1001 | 断开连接 |
| 1002 | 未授权 |
| 1003 | 请求过多 |
| 1004 | 重复请求 |
| 1005 | 无此接口 |
| 2001 | 余额不足 |
| 2002 | 订单不存在 |
| 2003 | 价格超出限制 |
| 2004 | 数量太小 |
| 2005 | 市场关闭 |

## 限流规则

- REST API: 1200 请求/分钟
- WebSocket: 100 订阅/连接
- 下单: 100 订单/10秒

## SDK

提供以下语言的 SDK：
- Python
- JavaScript/Node.js
- Java
- Go
- C#

详细使用说明请参考各 SDK 文档。