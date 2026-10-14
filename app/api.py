"""API 路由：品牌/词库管理、手动采样、指标查询、缺口、周报、告警。"""
from __future__ import annotations

import csv
import io
import os
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Alert, Brand, ContentItem, Keyword, Report, SamplingTask
from app.services import metrics, notifier, reporter
from app.services.scraper import scraper_service

router = APIRouter(prefix="/api", tags=["geo"])

# 创建品牌时自动展开的默认场景词（可传 scenarios 覆盖）
DEFAULT_SCENARIOS = ["是什么", "怎么样", "值得推荐吗", "价格怎么样", "和竞品比怎么样"]

# 品类通用问题模板（做商品/服务的客户：AI 回答"有哪些咖啡推荐"这类一般性问题时，你的品牌是否被提到/推荐）
# {category} 会被替换为品牌的品类词（如"咖啡"）
CATEGORY_SCENARIOS = [
    "有哪些{category}推荐",
    "什么{category}好",
    "{category}哪个牌子好",
    "{category}怎么选",
    "推荐一个{category}品牌",
    "买{category}要注意什么",
]

# 默认监控的 AI 引擎（多引擎对比是 GEO 核心价值；可传 engines 覆盖）
# wenxin 免登录可用排首位；kimi/doubao/yuanbao 需先手动登录一次（见 README）
DEFAULT_ENGINES = ["wenxin", "kimi", "doubao", "yuanbao"]


# ---------- 请求模型 ----------

class BrandCreate(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    industry: str = ""
    category: str = ""                        # 品类词（商品/服务客户），如"咖啡"；留空则不建品类通用问题
    official_domain: str = ""
    competitor_ids: list[int] = Field(default_factory=list)
    monitored_urls: list[str] = Field(default_factory=list)   # 自媒体客户：要追踪引用的内容 URL（RAG 监控）
    scenarios: list[str] | None = None        # 覆盖默认品牌场景词
    engines: list[str] | None = None          # 覆盖默认引擎列表
    frequency_hours: int | None = None        # 默认取 settings


class KeywordCreate(BaseModel):
    query_text: str
    scenario: str = ""
    priority: int = 1


class SamplingRun(BaseModel):
    brand_id: int | None = None
    task_ids: list[int] | None = None


class TaskPatch(BaseModel):
    """任务启停 / 改采样频率。"""
    status: str | None = Field(default=None, pattern="^(active|paused)$")
    frequency_hours: int | None = Field(default=None, ge=1)


class AlertConfig(BaseModel):
    """品牌告警阈值配置。"""
    negative_threshold: int | None = Field(default=None, ge=0)
    visibility_drop: float | None = Field(default=None, ge=0.0, le=1.0)


# ---------- 品牌与词库 ----------

@router.post("/brands", status_code=201)
def create_brand(payload: BrandCreate, db: Session = Depends(get_db)):
    """创建品牌，自动展开 品牌词×场景词 与 品类词×通用问题，并建多引擎采样任务。"""
    if db.query(Brand).filter(Brand.name == payload.name).first():
        raise HTTPException(409, f"品牌 {payload.name} 已存在")

    brand = Brand(
        name=payload.name,
        aliases=payload.aliases,
        industry=payload.industry,
        category=payload.category,
        official_domain=payload.official_domain,
        competitor_ids=payload.competitor_ids,
        monitored_urls=payload.monitored_urls,
    )
    db.add(brand)
    db.flush()

    engines = payload.engines or DEFAULT_ENGINES
    scenarios = payload.scenarios or DEFAULT_SCENARIOS
    task_count = 0
    kw_count = 0

    def add_keyword(query_text: str, scenario: str, ktype: str) -> None:
        nonlocal kw_count, task_count
        kw = Keyword(brand_id=brand.id, query_text=query_text, scenario=scenario, type=ktype)
        db.add(kw)
        db.flush()
        for eng in engines:
            db.add(SamplingTask(
                keyword_id=kw.id,
                engine=eng,
                frequency_hours=payload.frequency_hours or 24,
            ))
            task_count += 1
        kw_count += 1

    # 品牌词 × 场景词（type=brand）
    for qn in [payload.name] + payload.aliases:
        for sc in scenarios:
            add_keyword(f"{qn} {sc}", sc, "brand")

    # 品类词 × 通用问题（type=category）—— AI 推荐场景
    if payload.category:
        for tpl in CATEGORY_SCENARIOS:
            add_keyword(tpl.format(category=payload.category), "品类推荐", "category")

    db.commit()
    return {
        "brand_id": brand.id,
        "keywords_created": kw_count,
        "tasks_created": task_count,
        "engines": engines,
    }


@router.get("/brands")
def list_brands(db: Session = Depends(get_db)):
    return [
        {"id": b.id, "name": b.name, "industry": b.industry,
         "official_domain": b.official_domain, "competitor_ids": b.competitor_ids}
        for b in db.query(Brand).all()
    ]


@router.get("/brands/{brand_id}")
def get_brand(brand_id: int, db: Session = Depends(get_db)):
    brand = db.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(404, "brand 不存在")
    keywords = db.query(Keyword).filter(Keyword.brand_id == brand_id).all()
    competitors = [db.get(Brand, cid) for cid in (brand.competitor_ids or [])]
    return {
        "id": brand.id,
        "name": brand.name,
        "aliases": brand.aliases,
        "industry": brand.industry,
        "official_domain": brand.official_domain,
        "competitor_ids": brand.competitor_ids,
        "competitors": [{"id": c.id, "name": c.name} for c in competitors if c],
        "alert_negative_threshold": brand.alert_negative_threshold,
        "alert_visibility_drop": brand.alert_visibility_drop,
        "keywords": [{"id": k.id, "query_text": k.query_text, "scenario": k.scenario} for k in keywords],
    }


@router.patch("/brands/{brand_id}/alerts")
def update_alert_config(brand_id: int, payload: AlertConfig, db: Session = Depends(get_db)):
    """品牌级告警阈值配置（负面提及条数 / 可见度下降百分点）。"""
    brand = db.get(Brand, brand_id)
    if brand is None:
        raise HTTPException(404, "brand 不存在")
    if payload.negative_threshold is not None:
        brand.alert_negative_threshold = payload.negative_threshold
    if payload.visibility_drop is not None:
        brand.alert_visibility_drop = payload.visibility_drop
    db.commit()
    return {"negative_threshold": brand.alert_negative_threshold,
            "visibility_drop": brand.alert_visibility_drop}


@router.post("/brands/{brand_id}/keywords", status_code=201)
def add_keyword(brand_id: int, payload: KeywordCreate, db: Session = Depends(get_db)):
    if db.get(Brand, brand_id) is None:
        raise HTTPException(404, "brand 不存在")
    kw = Keyword(brand_id=brand_id, query_text=payload.query_text,
                 scenario=payload.scenario, priority=payload.priority)
    db.add(kw)
    db.flush()
    db.add(SamplingTask(keyword_id=kw.id, engine="kimi", frequency_hours=24))
    db.commit()
    return {"keyword_id": kw.id}


# ---------- 采样 ----------

@router.post("/sampling/run")
def run_sampling(payload: SamplingRun, background: BackgroundTasks,
                 db: Session = Depends(get_db)):
    """手动触发采样（后台执行，不阻塞请求）。"""
    if payload.brand_id:
        task_ids = [
            t.id for t in db.query(SamplingTask)
            .join(Keyword, SamplingTask.keyword_id == Keyword.id)
            .filter(Keyword.brand_id == payload.brand_id).all()
        ]
    elif payload.task_ids:
        task_ids = payload.task_ids
    else:
        task_ids = [t.id for t in db.query(SamplingTask).filter(SamplingTask.status == "active").all()]
    if not task_ids:
        return {"message": "没有可执行的任务"}

    background.add_task(scraper_service.run_task_ids, task_ids)
    return {"message": f"已提交 {len(task_ids)} 个采样任务到后台执行"}


@router.get("/sampling/tasks")
def list_tasks(db: Session = Depends(get_db)):
    return [
        {"id": t.id, "keyword_id": t.keyword_id, "engine": t.engine,
         "frequency_hours": t.frequency_hours, "status": t.status,
         "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
         "last_error": t.last_error}
        for t in db.query(SamplingTask).all()
    ]


@router.patch("/sampling/tasks/{task_id}")
def patch_task(task_id: int, payload: TaskPatch, db: Session = Depends(get_db)):
    """任务启停 / 改采样频率。paused 的任务调度器与手动采样都会跳过。"""
    task = db.get(SamplingTask, task_id)
    if task is None:
        raise HTTPException(404, "task 不存在")
    if payload.status is not None:
        task.status = payload.status
    if payload.frequency_hours is not None:
        task.frequency_hours = payload.frequency_hours
    db.commit()
    return {"id": task.id, "status": task.status, "frequency_hours": task.frequency_hours}


# ---------- 引擎维护 ----------

@router.post("/engines/login/{engine}")
def engine_login(engine: str, background: BackgroundTasks):
    """引导登录：有头模式打开该引擎页面，用户手动登录后关窗，cookie 自动保存。"""
    try:
        from app.services import engines as eng_mod
        eng_mod.get_adapter(engine)
    except KeyError as exc:
        raise HTTPException(404, str(exc))
    background.add_task(scraper_service.open_login_page, engine)
    return {"message": f"已打开 {engine} 登录窗口（约 5 分钟），请完成登录后关闭窗口"}


@router.post("/engines/probe")
def engines_probe():
    """探活全部已注册引擎：输入框可达性（判断登录态/风控）。约 1 分钟内返回。"""
    from app.services.probe import probe_all
    return {"results": probe_all()}


# ---------- 分析 ----------

@router.get("/analytics/visibility/{brand_id}")
def get_visibility(brand_id: int, db: Session = Depends(get_db)):
    vis = metrics.brand_visibility(db, brand_id)
    if "error" in vis:
        raise HTTPException(404, vis["error"])
    return vis


@router.get("/analytics/gaps/{brand_id}")
def get_gaps(brand_id: int, db: Session = Depends(get_db)):
    """答案缺口：竞品在、你不在的查询。gaps 按引擎拆分。"""
    return {
        "gaps": metrics.answer_gaps(db, brand_id),
        "by_engine": metrics.answer_gaps_by_engine(db, brand_id),
    }


@router.get("/analytics/content/{brand_id}")
def get_content_citations(brand_id: int, hours: int | None = None,
                          db: Session = Depends(get_db)):
    """自媒体/RAG 内容引用追踪：brands.monitored_urls 中的内容被 AI 引用的明细。"""
    return metrics.content_citations(db, brand_id, hours=hours)


@router.get("/analytics/trend/{brand_id}")
def get_visibility_trend(brand_id: int, limit: int = 30, db: Session = Depends(get_db)):
    """可见度历史趋势：来自采样快照（snapshots 表），按时间升序返回最近 limit 行。"""
    from app.services.snapshot import brand_trend
    return {"brand_id": brand_id, "trend": brand_trend(db, brand_id, limit=limit)}


@router.get("/analytics/compare")
def compare_visibility(ids: str, db: Session = Depends(get_db)):
    """竞品对比：ids 逗号分隔的品牌 id，同一口径返回可见度/SOV/引用/负面。"""
    try:
        brand_ids = [int(x) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(422, "ids 需为逗号分隔的数字")
    if not brand_ids:
        raise HTTPException(422, "ids 为空")
    return {"items": metrics.compare_brands(db, brand_ids)}


@router.get("/export/citations/{brand_id}")
def export_citations_csv(brand_id: int, db: Session = Depends(get_db)):
    """引用明细 CSV 导出（Excel 可直接打开，含 BOM）。"""
    from app.models import AIResponse, Citation, Keyword, SamplingTask
    if db.get(Brand, brand_id) is None:
        raise HTTPException(404, "brand 不存在")
    rows = (
        db.query(Keyword, SamplingTask, AIResponse, Citation)
        .join(SamplingTask, SamplingTask.keyword_id == Keyword.id)
        .join(AIResponse, AIResponse.task_id == SamplingTask.id)
        .join(Citation, Citation.response_id == AIResponse.id)
        .filter(Keyword.brand_id == brand_id)
        .order_by(AIResponse.sampled_at.desc())
        .all()
    )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["查询词", "引擎", "引用 URL", "域名", "采样时间", "引用片段"])
    for kw, task, resp, cit in rows:
        writer.writerow([
            kw.query_text, resp.engine, cit.url, cit.domain,
            resp.sampled_at.strftime("%Y-%m-%d %H:%M"), cit.snippet[:80],
        ])
    data = "\ufeff" + buf.getvalue()  # utf-8 BOM：Excel 打开不乱码
    return Response(content=data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="citations_{brand_id}.csv"'})


# ---------- 内容优化（GEO 第三层） ----------

@router.get("/content/brief/{brand_id}")
def get_content_brief(brand_id: int, db: Session = Depends(get_db)):
    """AI-ready 内容 Brief：基于缺口数据生成选题/FAQ/结构化清单/权威度动作。"""
    from app.services.content import generate_brief
    result = generate_brief(db, brand_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return {k: v for k, v in result.items() if k != "structure" or True} | {"structure": result.get("structure", {})}


@router.get("/content/authority/{brand_id}")
def get_authority_score(brand_id: int, db: Session = Depends(get_db)):
    """权威度建设：高权重域名被 AI 引用的统计 + 目标权威域动作清单。"""
    from app.services.content import authority_score
    result = authority_score(db, brand_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


@router.post("/content/check-index/{brand_id}")
def run_index_check(brand_id: int, engine: str = "wenxin", db: Session = Depends(get_db)):
    """索引保障：对 monitored_urls 的内容 URL 问 AI，验证是否已收录（后台执行）。"""
    from app.services.content import check_index
    try:
        result = check_index(db, brand_id, engine=engine)
    except Exception as exc:
        raise HTTPException(500, f"索引检查失败：{str(exc)[:300]}")
    if "error" in result:
        raise HTTPException(404, result["error"])
    return result


# ---------- 报告 ----------

@router.post("/reports/weekly/{brand_id}")
def create_weekly_report(brand_id: int, db: Session = Depends(get_db)):
    result = reporter.generate_weekly_report(db, brand_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    # 报告文件路径写回 metrics_json，供控制台"打开报告"直接定位
    report = db.get(Report, result["report_id"])
    if report is not None and report.metrics_json:
        report.metrics_json = {**report.metrics_json, "path": result.get("path", "")}
        db.commit()
    return result


@router.post("/reports/engine/{brand_id}")
def create_engine_report(brand_id: int, db: Session = Depends(get_db)):
    """生成跨引擎对比 HTML 报告（浏览器直接打开），并登记到 reports 表。"""
    from app.services.engine_report import generate_engine_report
    try:
        result = generate_engine_report(db, brand_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc))
    # 登记历史（与周报同口径：period = 最近 7 天）
    import os
    from datetime import timedelta
    report = Report(
        brand_id=brand_id,
        period_start=datetime.utcnow() - timedelta(days=7),
        period_end=datetime.utcnow(),
        metrics_json={"path": result.get("path", "")},
        content_md="",
    )
    db.add(report)
    db.commit()
    return {**result, "report_id": report.id}


@router.get("/reports")
def list_reports(brand_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(Report).order_by(Report.created_at.desc())
    if brand_id:
        q = q.filter(Report.brand_id == brand_id)
    return [
        {"id": r.id, "brand_id": r.brand_id, "period_start": r.period_start.isoformat(),
         "period_end": r.period_end.isoformat(), "created_at": r.created_at.isoformat(),
         "path": os.path.abspath((r.metrics_json or {}).get("path", ""))}
        for r in q.limit(50).all()
    ]


# ---------- 告警 ----------

@router.post("/alerts/check")
def run_alert_check(db: Session = Depends(get_db)):
    return {"created": notifier.check_all_brands()}


@router.get("/alerts")
def list_alerts(brand_id: int | None = None, unresolved_only: bool = False,
                db: Session = Depends(get_db)):
    q = db.query(Alert).order_by(Alert.created_at.desc())
    if brand_id:
        q = q.filter(Alert.brand_id == brand_id)
    if unresolved_only:
        q = q.filter(Alert.is_resolved.is_(False))
    return [
        {"id": a.id, "brand_id": a.brand_id, "type": a.type, "severity": a.severity,
         "detail": a.detail, "is_resolved": a.is_resolved, "created_at": a.created_at.isoformat()}
        for a in q.limit(50).all()
    ]


@router.post("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "alert 不存在")
    alert.is_resolved = True
    db.commit()
    return {"ok": True}


# ---------- 账号 GEO（自媒体/内容型客户视角） ----------

class ContentItemCreate(BaseModel):
    """新增监控内容：URL + 可选平台/发布时间。"""
    brand_id: int
    url: str
    platform: str = ""                       # 留空则按域名自动识别
    published_at: str = ""                   # ISO 格式，如 2026-09-01 或 2026-09-01T10:00:00


class ContentItemPatch(BaseModel):
    platform: str | None = None
    published_at: str | None = None          # 空字符串 = 清除发布时间


def _parse_dt(s: str):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        try:
            return datetime.strptime(s, "%Y-%m-%d")
        except Exception:
            return None


@router.get("/account/summary/{brand_id}")
def account_summary(brand_id: int, hours: int | None = None, db: Session = Depends(get_db)):
    """账号 GEO 总览：内容被引率 / 内容级 RAG 归因（哪篇哪句话）/ 收录时效 / 跨平台归因 / 账号对比。"""
    from app.services import account as account_svc
    return account_svc.account_summary(db, brand_id, hours)


@router.get("/account/compare")
def account_compare(ids: str, db: Session = Depends(get_db)):
    """同领域账号对比：内容被引维度（谁的内容更容易被 AI 引用）。"""
    from app.services import account as account_svc
    bid_list = [int(x) for x in ids.split(",") if x.strip().isdigit()]
    return account_svc.account_compare(db, bid_list)


@router.get("/account/content-items/{brand_id}")
def list_content_items(brand_id: int, db: Session = Depends(get_db)):
    """内容清单：URL/平台/发布时间/创建时间。"""
    from app.services import account as account_svc
    account_svc.sync_content_items(db, brand_id)
    rows = db.query(ContentItem).filter(ContentItem.brand_id == brand_id).order_by(ContentItem.id.desc()).all()
    return [
        {"id": c.id, "brand_id": c.brand_id, "url": c.url, "platform": c.platform,
         "published_at": c.published_at.isoformat() if c.published_at else None,
         "created_at": c.created_at.isoformat()}
        for c in rows
    ]


@router.post("/account/content-items", status_code=201)
def add_content_item(body: ContentItemCreate, db: Session = Depends(get_db)):
    """新增监控内容（同步写入 brands.monitored_urls 保持双写一致）。"""
    from app.services import account as account_svc
    brand = db.get(Brand, body.brand_id)
    if brand is None:
        raise HTTPException(404, "brand 不存在")
    url = (body.url or "").strip()
    if not url:
        raise HTTPException(422, "url 不能为空")
    platform = body.platform.strip() or account_svc.platform_of(url, brand.official_domain)
    item = ContentItem(brand_id=brand.id, url=url, platform=platform,
                       published_at=_parse_dt(body.published_at))
    db.add(item)
    murls = list(brand.monitored_urls or [])
    if url not in murls:
        murls.append(url)
        brand.monitored_urls = murls
    db.commit()
    db.refresh(item)
    return {"id": item.id, "url": item.url, "platform": item.platform,
            "published_at": item.published_at.isoformat() if item.published_at else None}


@router.patch("/account/content-items/{item_id}")
def patch_content_item(item_id: int, body: ContentItemPatch, db: Session = Depends(get_db)):
    """更新内容元数据（平台/发布时间）。"""
    item = db.get(ContentItem, item_id)
    if item is None:
        raise HTTPException(404, "内容不存在")
    if body.platform is not None:
        item.platform = body.platform.strip() or item.platform
    if body.published_at is not None:
        item.published_at = _parse_dt(body.published_at) or None
    db.commit()
    return {"ok": True, "id": item.id, "platform": item.platform,
            "published_at": item.published_at.isoformat() if item.published_at else None}


@router.delete("/account/content-items/{item_id}")
def delete_content_item(item_id: int, db: Session = Depends(get_db)):
    """删除监控内容（同步从 brands.monitored_urls 移除）。"""
    item = db.get(ContentItem, item_id)
    if item is None:
        raise HTTPException(404, "内容不存在")
    brand = db.get(Brand, item.brand_id)
    if brand is not None:
        murls = [u for u in (brand.monitored_urls or []) if u != item.url]
        brand.monitored_urls = murls
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.post("/reports/account/{brand_id}")
def create_account_report(brand_id: int, db: Session = Depends(get_db)):
    """生成账号 GEO 周报（内容被引/收录时效/平台归因），并把文件路径登记入库。"""
    from app.services import reporter as reporter_svc
    result = reporter_svc.generate_account_report(db, brand_id)
    if "error" in result:
        raise HTTPException(404, result["error"])
    report = Report(
        brand_id=brand_id,
        period_start=datetime.utcnow() - __import__("datetime").timedelta(days=7),
        period_end=datetime.utcnow(),
        metrics_json={"path": result.get("path", "")},
        content_md="",
    )
    db.add(report)
    db.commit()
    return {**result, "report_id": report.id}
