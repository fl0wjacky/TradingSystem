#!/usr/bin/env python3
"""
Mag API Server
提供HTTP API接口用于导入和分析数据
"""
from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Optional, List
import os
import tempfile
from datetime import datetime

from src.mag_reanalyze import reanalyze_date_range_json
from src.mag_system import import_and_analyze_json

# 创建FastAPI应用
app = FastAPI(
    title="Mag API",
    description="Mag交易系统数据导入和分析API",
    version="1.0.0"
)


# ========== 请求模型 ==========

class ImportRequest(BaseModel):
    """导入并分析请求"""
    notion_url: str = Field(..., description="Notion数据链接", example="https://serious-club-96d.notion.site/...")
    auto_analyze: bool = Field(True, description="是否自动分析（目前总是进行分析）")

    class Config:
        schema_extra = {
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
    verbose: bool = Field(False, description="是否显示详细分析结果（暂不支持）")
    export_txt: bool = Field(True, description="是否导出TXT文件")
    export_html: bool = Field(False, description="是否导出HTML文件")

    class Config:
        schema_extra = {
            "example": {
                "start_date": "2025-10-29",
                "end_date": "2025-10-29",
                "coins": None,
                "verbose": False,
                "export_txt": True,
                "export_html": True
            }
        }


# ========== API端点 ==========

@app.get("/")
async def root():
    """根路径，返回API信息"""
    return {
        "name": "Mag API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "import": "POST /api/v1/import",
            "reanalyze": "POST /api/v1/reanalyze",
            "download": "GET /api/v1/download/{filename}"
        }
    }


@app.post("/api/v1/import")
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


@app.post("/api/v1/reanalyze")
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
            export_txt=request.export_txt,
            export_html=request.export_html
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


@app.get("/api/v1/download/{filename}")
async def download_file(
    filename: str = Path(..., description="文件名，格式：mag_analysis_*.html 或 mag_analysis_*.txt")
):
    """
    下载生成的HTML或TXT文件

    只允许下载 mag_analysis_*.html 或 mag_analysis_*.txt 格式的文件，防止路径遍历攻击。
    """
    # 安全检查：只允许下载特定格式的文件
    if not filename.startswith("mag_analysis_"):
        raise HTTPException(
            status_code=400,
            detail="只允许下载 mag_analysis_* 格式的文件"
        )

    if not (filename.endswith(".html") or filename.endswith(".txt")):
        raise HTTPException(
            status_code=400,
            detail="只允许下载 .html 或 .txt 格式的文件"
        )

    # 防止路径遍历攻击
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=400,
            detail="文件名包含非法字符"
        )

    # 构建文件路径（从/tmp目录）
    file_path = os.path.join(tempfile.gettempdir(), filename)

    # 检查文件是否存在
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail=f"文件不存在: {filename}"
        )

    # 根据文件扩展名设置 media_type
    media_type = "text/html" if filename.endswith(".html") else "text/plain"

    # 返回文件
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )


# ========== 健康检查 ==========

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8888)
