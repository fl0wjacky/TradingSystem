# Mag 现货提示系统 - 项目结构

## 项目概述
Mag 场外体系是一个加密货币/股票现货交易分析系统，通过场外指数、爆破指数等多维度指标，提供进退场期判断和质量评级。

## 目录结构

```
mag/
├── .claude/                      # Claude Code 配置目录
│   └── settings.local.json      # 本地设置
│
├── src/                         # 源代码目录
│   ├── __init__.py              # 包初始化文件
│   │
│   ├── 核心模块 (Core Modules)
│   │   ├── database.py          # 数据库层 - SQLite 操作、数据持久化
│   │   ├── notion_scraper.py    # 数据抓取层 - Notion 数据解析
│   │   ├── analyzer.py          # 分析引擎 - 关键节点检测、质量判定
│   │   └── advisor.py           # 建议生成器 - 三类投资者分级建议
│   │
│   └── 主程序 (Main Programs)
│       ├── mag_system.py        # 系统主入口 - 完整分析流程
│       ├── mag_import.py        # 数据导入工具 - 支持手动/CSV/JSON/HTML
│       ├── mag_reanalyze.py     # 重新分析工具 - 支持日期范围重算
│       └── quick_import.py      # 快速导入脚本
│
├── tests/                       # 测试目录
│   ├── __init__.py              # 测试包初始化文件
│   ├── test_phase_logic.py      # 进退场期逻辑测试
│   ├── test_us_stock_detection.py # 美股识别逻辑测试
│   ├── test_approaching_correction.py # 逼近修正测试
│   └── test_multiple_break200.py # 多次跌破200测试
│
├── migrations/                  # 数据库迁移目录
│   ├── add_approaching_field.py # 添加逼近字段迁移脚本
│   └── fix_aave_us_stock.py     # 修复 AAVE 美股标记错误
│
├── 数据文件 (Data Files)
│   ├── mag_data.db              # SQLite 数据库 - 存储所有币种数据
│   ├── flow的笔记.html          # 浮墨笔记 HTML 导出文件
│   ├── mag_import_template.csv  # CSV 导入模板
│   └── mag_import_template.json # JSON 导入模板
│
├── 文档 (Documentation)
│   ├── README.md                # 项目说明文档
│   ├── CHANGELOG.md             # 版本更新日志
│   ├── 数据录入指南.md         # 数据录入操作指南
│   ├── mag.md                   # Mag 体系详细说明
│   ├── mvp.md                   # MVP 开发计划
│   └── PROJECT_STRUCTURE.md     # 本文件 - 项目结构说明
│
└── 依赖配置 (Dependencies)
    └── requirements.txt         # Python 依赖包列表
```

## 核心模块说明

### 1. database.py - 数据库层
**职责**: SQLite 数据库操作、数据持久化

**核心功能**:
- 数据库初始化和表结构管理
- 币种数据的 CRUD 操作
- 支持乱序和缺失日期的查询方法:
  - `get_previous_day_data()` - 查找真正的前一天
  - `get_next_day_data()` - 查找真正的后一天
  - `find_crossing_node()` - 通用的跨越节点查找
- 分析结果保存和查询

**数据表**:
- `coin_daily_data` - 每日币种数据
- `analysis_results` - 分析结果记录

### 2. notion_scraper.py - 数据抓取层
**职责**: 解析 Notion 页面文本，提取币种数据

**核心功能**:
- 支持 4 种数据格式自动识别:
  - 格式1: 标准格式 (场外指数+进退场期在同一行)
  - 格式2: 紧凑格式 (爆破指数在同一行，支持中文币名)
  - 格式3: 币名单独一行
  - 格式4: 特殊格式 (地产等)
- 状态机解析 - 支持"大宗$美股区"区域标记
- 特殊处理:
  - 美股识别 (区域标记 + 完全匹配)
  - 黄金识别 (统一为 GOLD)
  - 原油识别 (统一为 OIL)
- 逼近关键字检测

### 3. analyzer.py - 分析引擎
**职责**: 核心分析算法，包括关键节点检测、插值计算、质量判定

**核心功能**:
- 4 种关键节点检测:
  - 进场期第一天
  - 退场期第一天
  - 爆破指数跌破 200
  - 爆破指数负转正
- 参考节点查找 (支持乱序和缺失日期)
- 场外指数变化百分比计算 (进退场期反向逻辑)
- 多维度修正计算:
  - 相变修正 (±5%)
  - 美股修正 (-10%)
  - 爆破指数修正 (-2.5%)
  - 逼近修正 (-5%)
- 质量评级 (优质/一般/劣质)
- 对标链验证 (美股→BTC→龙头币)

### 4. advisor.py - 建议生成器
**职责**: 根据分析结果生成三类投资者的分级建议

**核心功能**:
- 三类投资者建议:
  - 新手投资者 (保守策略)
  - 中级投资者 (平衡策略)
  - 高级投资者 (进取策略)
- 格式化输出 (Rich 库美化显示)
- 场外指数变化展示 (包含各项修正)

## 主程序说明

### mag_system.py - 系统主入口
完整的分析流程：数据录入 → 分析 → 建议生成

### mag_import.py - 数据导入工具
支持 4 种导入方式：
- 手动录入 (交互式)
- CSV 批量导入
- JSON 批量导入
- 浮墨笔记 HTML 导入

### mag_reanalyze.py - 重新分析工具
支持指定日期范围重新分析，用于：
- 补录数据后更新分析结果
- 修复逻辑后重算历史数据
- 指定币种重新分析

## 版本历史

### v2.3.0 (2025-10-16) - 最新版本
- 🐛 修复退场期涨幅计算逻辑错误
- 🐛 修复中文币名解析问题 (原油数据)

### v2.2.0 (2025-10-16)
- ✨ 新增逼近修正功能

### v2.1.0 (2025-10-16)
- ✨ 新增爆破指数修正

### v2.0.0 (2025-10-16)
- 🚀 支持乱序和缺失日期录入
- 🔧 重构数据库查询逻辑
- 🛠️ 新增重新分析工具

### v1.0.0 (2025-10-15)
- 🎉 首次发布 MVP 版本

## 技术栈

- **语言**: Python 3.9+
- **数据库**: SQLite
- **数据解析**: BeautifulSoup4, 正则表达式
- **CLI 美化**: Rich
- **测试**: 自定义测试脚本

## 数据流程

```
Notion 笔记
    ↓
浮墨笔记 HTML 导出
    ↓
notion_scraper.py 解析
    ↓
database.py 存储
    ↓
analyzer.py 分析
    ↓
advisor.py 生成建议
    ↓
控制台输出/数据库保存
```

## 开发约定

### 文件命名
- 核心模块: `模块名.py` (如 `analyzer.py`)
- 主程序: `mag_*.py` (如 `mag_import.py`)
- 测试文件: `test_*.py` (如 `test_phase_logic.py`)
- 工具脚本: `功能描述.py` (如 `fix_aave_us_stock.py`)

### Git 提交规范
- `feat:` 新功能
- `fix:` Bug 修复
- `docs:` 文档更新
- `refactor:` 代码重构
- `test:` 测试相关

## 快速开始

```bash
# 1. 安装依赖
pip3 install -r requirements.txt

# 2. 手动录入数据
python3 mag_import.py manual

# 3. 导入 HTML 文件
python3 mag_import.py html "flow的笔记.html"

# 4. 运行分析
python3 mag_system.py

# 5. 重新分析指定日期
python3 mag_reanalyze.py 2025-10-10 2025-10-15
```

## 贡献者

- Flow - 系统设计与实现
- Claude Code - 开发辅助

## 许可证

MIT License
