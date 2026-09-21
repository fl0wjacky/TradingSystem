#!/usr/bin/env python3
"""
Mag API Server
提供HTTP API接口用于导入和分析数据
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import os
import secrets

from src.mag_reanalyze import reanalyze_date_range_json
from src.mag_system import import_and_analyze_json
from src.gen_chart import load_data, load_coin_nodes, render_page

# 创建FastAPI应用
# docs/redoc/openapi 一律不注册:此服务经 Cloudflare Tunnel 暴露在公网
# (magtrading.surfers.cc),不需要交互式文档,少三个端点就少三份暴露面。
app = FastAPI(
    title="Mag API",
    description="Mag交易系统数据导入和分析API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

# 写接口鉴权(公网上唯一的一层)
#
# .env 里的 MAG_API_KEY;复用项目自己的 .env 解析,不引入 python-dotenv 依赖。
# 改了 key 需要重启服务:launchctl kickstart -k gui/$(id -u)/cc.surfers.magtrading
#
# 这里原本还有一层 ALLOWED_NETWORKS / check_ip_restriction 的 IP 白名单,已移除。
# 原因:uvicorn 默认 proxy_headers=True,会解析 cloudflared 传来的 X-Forwarded-For,
# 所以它看到的是访问者的真实公网 IP(不是 127.0.0.1)。这意味着经 tunnel 来的请求
# 一律不在白名单内 —— 带正确 key 也会被 403 挡掉,写接口从外网彻底不可用。
# 既然本就要求 X-API-Key,IP 白名单只剩副作用,故删。
from src.config import config as _env_config

_env_config.load_from_env()
API_KEY = os.environ.get('MAG_API_KEY', '')


async def require_api_key(x_api_key: str = Header(default='', alias='X-API-Key')):
    """校验请求头 X-API-Key。

    未配置 MAG_API_KEY 时一律拒绝(fail closed),避免配置缺失导致写接口裸奔。
    """
    if not API_KEY:
        raise HTTPException(
            status_code=503,
            detail="MAG_API_KEY 未配置,写接口已禁用"
        )
    try:
        ok = secrets.compare_digest(x_api_key.encode('utf-8'), API_KEY.encode('utf-8'))
    except Exception:
        ok = False
    if not ok:
        raise HTTPException(status_code=403, detail="Forbidden")


# ========== 请求模型 ==========

class ImportRequest(BaseModel):
    """导入并分析请求"""
    notion_url: str = Field(..., description="Notion数据链接", example="https://serious-club-96d.notion.site/...")
    auto_analyze: bool = Field(True, description="是否自动分析（目前总是进行分析）")

    class Config:
        json_schema_extra = {
            "example": {
                "notion_url": "https://serious-club-96d.notion.site/29b019fe17e080cf8f50c053afb95c80",
                "auto_analyze": True
            }
        }


class ReanalyzeRequest(BaseModel):
    """重新分析请求"""
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)", example="2025-10-29")
    end_date: Optional[str] = Field(None, description="结束日期 (YYYY-MM-DD)，默认等于start_date", example="2025-10-29")
    coins: Optional[List[str]] = Field(None, description="指定币种列表，null表示所有币种", example=["BTC", "ETH"])
    verbose: bool = Field(False, description="是否显示详细分析建议")
    no_altcoins: bool = Field(False, description="是否过滤掉山寨币，只显示美股、BTC、龙头币、国内A股")

    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2025-10-29",
                "end_date": "2025-10-29",
                "coins": None,
                "verbose": False,
                "no_altcoins": False
            }
        }


# ========== API端点 ==========

@app.get("/", include_in_schema=False)
async def root():
    """根路径直接跳到图表页。

    原先返回一份 API 端点清单,但这个服务在公网上只有图表是给人看的,
    列出写接口没有意义。访问 magtrading.surfers.cc 直接出图。
    """
    return RedirectResponse(url="/chart")


@app.post("/api/v1/import",
          dependencies=[Depends(require_api_key)])
async def import_data(request: ImportRequest):
    """
    导入Notion数据并分析

    从Notion链接抓取数据，存储到数据库，并分析所有关键节点。
    返回当天的关键节点和特殊节点列表。
    """
    # 验证URL格式（基本检查）
    if not request.notion_url.startswith("http"):
        raise HTTPException(
            status_code=400,
            detail="Notion URL格式不正确，必须以http开头"
        )

    # 执行导入和分析
    try:
        result = import_and_analyze_json(
            notion_url=request.notion_url,
            auto_analyze=request.auto_analyze
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("detail", result.get("error", "导入失败"))
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"导入过程出错: {str(e)}"
        )


@app.post("/api/v1/reanalyze",
          dependencies=[Depends(require_api_key)])
async def reanalyze(request: ReanalyzeRequest):
    """
    重新分析历史数据

    这个接口会删除指定日期范围的旧分析结果，然后重新分析。
    返回检测到的所有关键节点和特殊节点。
    """
    # 验证日期格式
    try:
        datetime.strptime(request.start_date, '%Y-%m-%d')
        end_date = request.end_date or request.start_date
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="日期格式不正确，请使用 YYYY-MM-DD 格式"
        )

    # 执行分析
    try:
        result = reanalyze_date_range_json(
            start_date=request.start_date,
            end_date=end_date,
            coins=request.coins,
            verbose=request.verbose,
            no_altcoins=request.no_altcoins
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=400,
                detail=result.get("detail", result.get("error", "分析失败"))
            )

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"分析过程出错: {str(e)}"
        )


# ========== 可视化页面 ==========

@app.get("/chart", response_class=HTMLResponse)
async def chart_page():
    """标的可视化页面。数据实时从数据库读取，运行 mag_system 导入后刷新即更新。"""
    return render_page("fetch('/chart/data').then(r => r.json()).then(d => { d.live = true; initChart(d); });")


@app.get("/chart/data")
async def chart_data():
    """可视化页面所需数据（实时读库）。

    页面加载时顺带触发 K 线刷新：若当天尚未更新，则在后台增量抓取并存库，
    一天最多一次——后续访问者直接读已缓存的当日 K 线，不重复拉取。
    """
    from src.fetch_kline import refresh_if_stale
    refresh_if_stale()
    return JSONResponse(load_data(include_nodes=False))  # 节点详情由 /chart/nodes 按标的懒加载


@app.get("/chart/nodes")
async def chart_nodes(coin: str):
    """单个标的的关键/特殊节点详情 {date: [节点...]}，页面切到该标的时懒加载并缓存。"""
    return JSONResponse(load_coin_nodes(coin))


PERSONALITIES = ['conservative', 'aggressive', 'middle_a', 'middle_b', 'middle_c', 'middle_d']


@app.get("/chart/backtest")
async def chart_backtest(coin: str, start: str, end: str, personality: str):
    """可视化页面的回测接口：以真实日 K 线中间价 (开+收)/2 成交，只在有 K 线的日期交易。

    回测前先对该标的在所选区间重新分析节点（只删除并重算这一个标的，其他标的不受影响，
    单标的全年约 1 秒），保证回测用的节点与当前数据和分析逻辑一致，不依赖过期的分析结果。
    返回交易明细与逐日资金曲线，供页面在 K 线上标注买卖点并叠加资金曲线。
    """
    from src.database import MagDatabase
    from src.config import MagConfig
    from src.backtest import BacktestEngine

    try:
        datetime.strptime(start, '%Y-%m-%d')
        datetime.strptime(end, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式不正确，请使用 YYYY-MM-DD 格式")
    if start > end:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    if personality not in PERSONALITIES:
        raise HTTPException(status_code=400, detail=f"性格类型必须是: {', '.join(PERSONALITIES)}")

    # 先重算该标的在区间内的节点；区间内没有场外数据时 reanalyze 返回失败，
    # 这不算错误（回测会按无节点处理），其余情况照常回测
    reanalyze_date_range_json(start_date=start, end_date=end, coins=[coin])

    config = MagConfig()
    engine = BacktestEngine(MagDatabase(config.db_path), config)
    result = engine.run_backtest(coin, start, end, personality, price_source='kline')
    if not result.get('success'):
        raise HTTPException(status_code=404, detail=result.get('error', '回测失败'))
    return JSONResponse(result)


# ========== 健康检查 ==========

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8888)
