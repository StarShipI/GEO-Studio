"""FastAPI 入口。运行：cd geo-studio && uvicorn app.main:app --reload"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.database import init_db
from app.scheduler import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="GEO Studio",
    description="GEO 服务型 MVP：AI 引擎引用监控 + 解析归因 + 指标与周报",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS：看板既走同源托管（/dashboard），也允许直接用文件打开时跨源调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

# 图形界面（web/ 目录）：看板 dashboard.html + 操作控制台 console.html
_WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")
os.makedirs(_WEB_DIR, exist_ok=True)


def _serve_page(name: str):
    from fastapi.responses import FileResponse
    return FileResponse(os.path.join(_WEB_DIR, name))


@app.get("/dashboard", include_in_schema=False)
def dashboard():
    return _serve_page("dashboard.html")


@app.get("/console", include_in_schema=False)
def console():
    return _serve_page("console.html")


@app.get("/account", include_in_schema=False)
def account():
    return _serve_page("account.html")


@app.get("/")
def root():
    return {
        "name": "GEO Studio",
        "dashboard": "/dashboard",
        "console": "/console",
        "docs": "/docs",
        "api": {
            "创建品牌": "POST /api/brands",
            "手动采样": "POST /api/sampling/run",
            "可见度": "GET /api/analytics/visibility/{brand_id}",
            "答案缺口": "GET /api/analytics/gaps/{brand_id}",
            "生成周报": "POST /api/reports/weekly/{brand_id}",
        },
    }
