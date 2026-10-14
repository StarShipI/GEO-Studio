# -*- coding: utf-8 -*-
"""账号 GEO 服务层：自媒体/内容型客户视角。

品牌 GEO 看"品牌名被 AI 提及"，账号 GEO 看"我的内容被 AI 引用"：
- 内容级 RAG 归因：AI 回答某问题时引用了哪篇内容的哪句话（citations.snippet）。
- 内容被引率：被引内容数 / 全部监控内容数。
- 收录时效：内容发布时间 → 首次被 AI 引用（采样发现）的间隔。
- 跨平台发布效果归因：按平台聚合内容数/被引内容数/被引率/引用次数。
- 同领域账号对比：多账号的内容被引维度并列。
"""
from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import AIResponse, Brand, Citation, ContentItem

# 域名 → 平台映射（跨平台归因的默认规则，可在控制台手动覆盖）
PLATFORM_RULES = [
    ("xiaohongshu.com", "小红书"),
    ("xhslink.com", "小红书"),
    ("mp.weixin.qq.com", "公众号"),
    ("weixin.qq.com", "微信"),
    ("zhihu.com", "知乎"),
    ("bilibili.com", "B站"),
    ("douyin.com", "抖音"),
    ("weibo.com", "微博"),
    ("baijiahao.baidu.com", "百家号"),
    ("toutiao.com", "头条"),
    ("juejin.cn", "掘金"),
    ("csdn.net", "CSDN"),
]

PLATFORM_CHOICES = ["小红书", "公众号", "知乎", "B站", "抖音", "微博", "百家号", "头条", "官网", "其他"]


def platform_of(url: str, official_domain: str | None = None) -> str:
    """按域名推断内容平台；品牌官方域名 → 官网，其余未命中 → 其他。"""
    try:
        d = urlparse(url).netloc.lower()
    except Exception:
        return "其他"
    for suffix, name in PLATFORM_RULES:
        if d == suffix or d.endswith("." + suffix):
            return name
    if official_domain:
        od = (official_domain or "").lower().replace("https://", "").replace("http://", "").strip("/")
        if od and (d == od or d.endswith("." + od)):
            return "官网"
    return "其他"


def sync_content_items(db: Session, brand_id: int) -> None:
    """把 brands.monitored_urls 中尚未登记的内容同步进 content_items（幂等）。"""
    brand = db.get(Brand, brand_id)
    if brand is None:
        return
    existing = {c.url for c in db.query(ContentItem).filter(ContentItem.brand_id == brand_id).all()}
    added = 0
    for u in (brand.monitored_urls or []):
        u = (u or "").strip()
        if not u or u in existing:
            continue
        db.add(ContentItem(brand_id=brand_id, url=u, platform=platform_of(u, brand.official_domain)))
        existing.add(u)
        added += 1
    if added:
        db.commit()


def _norm_url(u: str) -> str:
    u = (u or "").split("#")[0].split("?")[0].rstrip("/")
    return u.lower()


def _domain_matches(url_domain: str, item_url: str) -> bool:
    """内容匹配：精确 URL 优先，其次域名子域匹配（监控整站/专栏时可用）。"""
    u = _norm_url(item_url)
    if url_domain in u or u.endswith(url_domain):
        return True
    return False


def _fmt_duration(d: timedelta | None) -> str:
    """收录时效格式化：3 天 4 小时 / 12 小时 / 45 分钟。"""
    if d is None or d < timedelta(0):
        return "-"
    days, secs = d.days, d.seconds
    hours, mins = secs // 3600, (secs % 3600) // 60
    if days > 0:
        return f"{days} 天 {hours} 小时"
    if hours > 0:
        return f"{hours} 小时 {mins} 分钟"
    if mins > 0:
        return f"{mins} 分钟"
    return "刚收录"


def account_summary(db: Session, brand_id: int, hours: int | None = None) -> dict:
    """账号 GEO 总览：内容被引率、内容级 RAG 归因、收录时效、跨平台归因。"""
    brand = db.get(Brand, brand_id)
    if brand is None:
        return {"error": "brand 不存在"}
    sync_content_items(db, brand_id)

    items = db.query(ContentItem).filter(ContentItem.brand_id == brand_id).all()
    if not items:
        return {
            "brand_id": brand_id, "brand_name": brand.name,
            "content_count": 0, "cited_content_count": 0, "citation_rate": 0.0,
            "total_citations": 0, "avg_cited_duration": None,
            "items": [], "uncited": [], "platforms": [], "compare": [],
            "hint": "该品牌还没有监控内容。请在控制台「内容清单」添加公众号/小红书/知乎等平台的发布内容 URL。",
        }

    q = db.query(Citation, AIResponse).join(AIResponse, Citation.response_id == AIResponse.id)
    if hours:
        since = datetime.utcnow() - timedelta(hours=hours)
        q = q.filter(AIResponse.sampled_at >= since)

    # 内容 → 引用明细
    by_item: dict[int, list[dict]] = {it.id: [] for it in items}
    for cit, resp in q.all():
        hit = None
        for it in items:
            if _norm_url(cit.url) == _norm_url(it.url):
                hit = it
                break
        if hit is None:
            for it in items:
                try:
                    if urlparse(cit.url).netloc.lower() == urlparse(it.url).netloc.lower():
                        hit = it
                        break
                except Exception:
                    pass
        if hit is None:
            continue
        by_item[hit.id].append({
            "citation_id": cit.id,
            "url": cit.url,
            "query": resp.prompt_text,
            "engine": resp.engine,
            "sampled_at": resp.sampled_at.isoformat(),
            "snippet": cit.snippet,          # 引用所在的一句话（哪句话）
            "position": cit.position,
        })

    now = datetime.utcnow()
    item_rows, uncited, total_citations = [], [], 0
    cited_times: list[timedelta] = []
    platform_stat: dict[str, dict] = {}

    for it in items:
        cites = sorted(by_item[it.id], key=lambda x: x["sampled_at"])
        count = len(cites)
        total_citations += count
        first_cited_at = cites[0]["sampled_at"] if cites else None
        first_cited_dt = datetime.fromisoformat(first_cited_at) if first_cited_at else None
        duration = None
        if first_cited_dt and it.published_at:
            duration = first_cited_dt - it.published_at
            if duration >= timedelta(0):
                cited_times.append(duration)
        ps = platform_stat.setdefault(it.platform or platform_of(it.url), {
            "platform": it.platform or platform_of(it.url), "content_count": 0,
            "cited_count": 0, "citations": 0, "durations": [],
        })
        ps["content_count"] += 1
        if count:
            ps["cited_count"] += 1
            ps["citations"] += count
            if duration is not None:
                ps["durations"].append(duration)
        row = {
            "id": it.id, "url": it.url, "platform": it.platform or platform_of(it.url),
            "published_at": it.published_at.isoformat() if it.published_at else None,
            "citation_count": count,
            "first_cited_at": first_cited_at,
            "duration": _fmt_duration(duration),
            "citations": cites[:8],
        }
        if count:
            item_rows.append(row)
        else:
            uncited.append(row)

    item_rows.sort(key=lambda x: -x["citation_count"])
    uncited.sort(key=lambda x: (x["published_at"] or "0"), reverse=True)

    platforms = []
    for p in platform_stat.values():
        platforms.append({
            "platform": p["platform"],
            "content_count": p["content_count"],
            "cited_count": p["cited_count"],
            "citation_rate": round(p["cited_count"] / p["content_count"], 4) if p["content_count"] else 0.0,
            "citations": p["citations"],
            "avg_duration": _fmt_duration(sum(p["durations"], timedelta()) / len(p["durations"])) if p["durations"] else None,
        })
    platforms.sort(key=lambda x: -x["citations"])

    cited_count = len(item_rows)
    return {
        "brand_id": brand_id,
        "brand_name": brand.name,
        "content_count": len(items),
        "cited_content_count": cited_count,
        "citation_rate": round(cited_count / len(items), 4) if items else 0.0,
        "total_citations": total_citations,
        "avg_cited_duration": _fmt_duration(sum(cited_times, timedelta()) / len(cited_times)) if cited_times else None,
        "items": item_rows,
        "uncited": uncited,
        "platforms": platforms,
        "compare": account_compare(db, [brand_id] + list(brand.competitor_ids or [])),
    }


def account_compare(db: Session, brand_ids: list[int]) -> list[dict]:
    """同领域账号对比：内容被引维度并列（谁的内容更容易被 AI 引用）。"""
    out = []
    for bid in brand_ids:
        brand = db.get(Brand, bid)
        if brand is None:
            continue
        sync_content_items(db, bid)
        items = db.query(ContentItem).filter(ContentItem.brand_id == bid).all()
        if not items:
            out.append({"brand_id": bid, "brand_name": brand.name, "content_count": 0,
                        "cited_content_count": 0, "citation_rate": 0.0, "total_citations": 0})
            continue
        q = db.query(Citation, AIResponse).join(AIResponse, Citation.response_id == AIResponse.id)
        urls = {_norm_url(it.url) for it in items}
        domains = set()
        for it in items:
            try:
                domains.add(urlparse(it.url).netloc.lower())
            except Exception:
                pass
        cited_ids = set()
        total = 0
        for cit, resp in q.all():
            nu = _norm_url(cit.url)
            if nu in urls:
                cited_ids.add(nu)
                total += 1
                continue
            try:
                d = urlparse(cit.url).netloc.lower()
            except Exception:
                continue
            if d in domains or any(d.endswith("." + dd) for dd in domains if dd):
                cited_ids.add(nu)
                total += 1
        out.append({
            "brand_id": bid, "brand_name": brand.name,
            "content_count": len(items),
            "cited_content_count": len(cited_ids),
            "citation_rate": round(len(cited_ids) / len(items), 4) if items else 0.0,
            "total_citations": total,
        })
    return out
