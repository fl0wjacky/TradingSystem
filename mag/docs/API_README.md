# Mag API 使用文档

## 概述

Mag API 提供HTTP接口用于Mag交易系统的数据导入和分析功能。

- **基地址**: `http://127.0.0.1:8888`
- **认证**: 无需认证（仅localhost使用）
- **响应格式**: JSON

## 快速开始

### 启动API服务器

```bash
# 方式1：使用启动脚本
./start_api.sh

# 方式2：直接启动
python3 -m uvicorn src.api:app --host 127.0.0.1 --port 8888
```

### 访问API文档

浏览器打开：
- Swagger UI: http://127.0.0.1:8888/docs
- ReDoc: http://127.0.0.1:8888/redoc

---

## API端点

### 1. 导入并分析数据

**端点**: `POST /api/v1/import`

从Notion链接导入数据，存储到数据库，并自动分析关键节点。

#### 请求

```bash
curl -X POST http://127.0.0.1:8888/api/v1/import \
  -H "Content-Type: application/json" \
  -d '{
    "notion_url": "https://serious-club-96d.notion.site/...",
    "auto_analyze": true
  }'
```

**请求参数**:
- `notion_url` (必填): Notion数据链接
- `auto_analyze` (可选): 是否自动分析，默认true（当前总是执行分析）

#### 成功响应 (200 OK)

```json
{
  "success": true,
  "message": "导入并分析完成",
  "data": {
    "date": "2025-10-29",
    "total_coins": 33,
    "key_nodes_count": 1,
    "special_nodes_count": 3,
    "statistics": {
      "enter_phase": 15,
      "exit_phase": 18
    },
    "key_nodes": [
      {
        "coin": "TSLA",
        "date": "2025-10-29",
        "node_type": "enter_phase_day1",
        "quality_rating": "劣质",
        "final_percentage": -40.2,
        "section_desc": "进场期第1小节质量",
        ...
      }
    ],
    "special_nodes": [
      {
        "coin": "AAPL",
        "date": "2025-10-29",
        "node_type": "offchain_below_1000",
        "description": "场外指数跌破1000 - 场外指数：981，爆破指数：225",
        "offchain": 981,
        "break": 225
      },
      ...
    ],
    "execution_time": "4.2s"
  }
}
```

#### 失败响应 (400/500)

```json
{
  "detail": "从Notion链接中未能解析到任何币种数据"
}
```

---

### 2. 重新分析历史数据

**端点**: `POST /api/v1/reanalyze`

重新分析指定日期范围的历史数据，可选择导出HTML报告。

#### 请求

```bash
curl -X POST http://127.0.0.1:8888/api/v1/reanalyze \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2025-10-29",
    "end_date": "2025-10-29",
    "coins": null,
    "export_html": true
  }'
```

**请求参数**:
- `start_date` (必填): 开始日期 (YYYY-MM-DD)
- `end_date` (可选): 结束日期，默认等于start_date
- `coins` (可选): 指定币种列表，如["BTC", "ETH"]，null表示所有币种
- `verbose` (可选): 是否显示详细结果（暂不支持）
- `export_html` (可选): 是否导出HTML文件，默认false

#### 成功响应 (200 OK)

```json
{
  "success": true,
  "message": "重新分析完成",
  "data": {
    "date_range": {
      "start": "2025-10-29",
      "end": "2025-10-29"
    },
    "total_records": 33,
    "analyzed_count": 33,
    "detected_nodes_count": 4,
    "nodes": [
      {
        "type": "special",
        "date": "2025-10-29",
        "coin": "AAPL",
        "node_type": "offchain_below_1000",
        "data": {
          "description": "场外指数跌破1000",
          "offchain": 981,
          "break": 225
        }
      },
      {
        "type": "key",
        "date": "2025-10-29",
        "coin": "TSLA",
        "node_type": "enter_phase_day1",
        "data": {
          "quality_rating": "劣质",
          "final_percentage": -40.2,
          ...
        }
      }
    ],
    "html_file": "mag_analysis_2025-10-29.html",
    "html_download_url": "/api/v1/download/mag_analysis_2025-10-29.html",
    "execution_time": "2.1s"
  }
}
```

---

### 3. 下载HTML报告

**端点**: `GET /api/v1/download/{filename}`

下载reanalyze生成的HTML分析报告。

#### 请求

```bash
curl http://127.0.0.1:8888/api/v1/download/mag_analysis_2025-10-29.html \
  > report.html
```

**路径参数**:
- `filename`: HTML文件名（格式：mag_analysis_*.html）

#### 成功响应 (200 OK)

返回HTML文件内容，Content-Type: text/html

#### 失败响应 (404)

```json
{
  "detail": "文件不存在: mag_analysis_2025-10-29.html"
}
```

---

## n8n集成示例

### 导入数据工作流

```
1. [Webhook/定时触发]
   ↓
2. [HTTP Request] POST /api/v1/import
   Body: {
     "notion_url": "{{$json.url}}"
   }
   ↓
3. [IF] 判断 {{$json.success}}
   ├─ True: 处理节点数据
   └─ False: 发送告警
```

### 重新分析工作流

```
1. [手动触发]
   ↓
2. [Set] 设置参数
   start_date: "2025-10-29"
   export_html: true
   ↓
3. [HTTP Request] POST /api/v1/reanalyze
   ↓
4. [IF] 是否生成HTML
   ├─ True: 下载HTML报告
   └─ False: 继续
```

### n8n节点配置示例

```javascript
// HTTP Request 节点
{
  "method": "POST",
  "url": "http://127.0.0.1:8888/api/v1/import",
  "body": {
    "notion_url": "{{$json.url}}"
  },
  "options": {
    "timeout": 30000
  }
}

// 处理响应数据
{{$json.data.key_nodes}}  // 关键节点列表
{{$json.data.total_coins}}  // 总币种数
```

---

## 错误码

| 状态码 | 说明 |
|--------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误（URL格式、日期格式等） |
| 404 | 文件不存在 |
| 500 | 服务器内部错误 |

---

## 数据结构说明

### 关键节点 (key_nodes)

关键节点类型：
- `enter_phase_day1`: 进场期第1天
- `exit_phase_day1`: 退场期第1天
- `break_200`: 爆破跌破200
- `break_0`: 爆破负转正

质量评级：
- `优质`: 高质量节点
- `一般`: 中等质量节点
- `劣质`: 低质量节点

### 特殊节点 (special_nodes)

特殊节点类型：
- `approaching`: 提示逼近
- `quality_warning_entry`: 进场期质量修正
- `quality_warning_exit`: 退场期质量修正
- `break_above_200`: 爆破指数超200
- `offchain_above_1000`: 场外指数超1000
- `offchain_below_1000`: 场外指数跌破1000

---

## 常见问题

### Q: API超时怎么办？
A: 默认响应时间在5秒内。如果Notion数据量很大，可能需要更长时间。建议设置30秒超时。

### Q: 可以同时调用多个API吗？
A: 建议串行调用。虽然技术上支持并发，但SQLite数据库可能会有写入锁。

### Q: 如何获取历史所有节点？
A: 使用 `POST /api/v1/reanalyze`，设置较大的日期范围，如 `2025-01-01` 到 `2025-12-31`。

### Q: HTML文件存放在哪里？
A: 生成的HTML文件保存在项目根目录（与start_api.sh同级）。

---

## 安全说明

- API仅监听localhost (127.0.0.1)，不对外网开放
- 无认证机制，仅供本地或可信环境使用
- 文件下载限制为mag_analysis_*.html格式，防止路径遍历攻击
- 不建议在生产环境直接使用，需要添加认证和权限控制

---

## 版本历史

### v1.0.0 (2025-10-29)
- 初始版本
- 实现import、reanalyze、download三个核心端点
- 支持JSON结构化响应
- 支持HTML报告导出
