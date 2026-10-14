"""指标计算：AI 可见度、引用份额（SOV）、答案缺口、负面提及。

所有指标都由明细（ai_responses / citations / brand_mentions）实时重算，
不存快照表 —— MVP 阶段数据量小，重算最省事且不怕脏数据。
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import AIResponse, Brand, BrandMention, Citation, Keyword, SamplingTask


def _latest_response_by_keyword(db: Session, brand_id: int) -> dict[int, AIResponse]:
    """每个关键词取最新一条回答快照。"""
    latest: dict[int, AIResponse] = {}
    rows = (
        db.query(Keyword, SamplingTask, AIResponse)
        .join(SamplingTask, SamplingTask.keyword_id == Keyword.id)
        .join(AIResponse, AIResponse.task_id == SamplingTask.id)
        .filter(Keyword.brand_id == brand_id)
        .order_by(AIResponse.sampled_at.desc())
        .all()
    )
    for kw, _task, resp in rows:
        if kw.id not in latest:
            latest[kw.id] = resp
    return latest


def _brand_names(brand: Brand) -> set[str]:
    names = {brand.name} | {str(a) for a in (brand.aliases or [])}
    return {n.strip().lower() for n in names if n and n.strip()}


def _domain_matches(url_domain: str, brand: Brand) -> bool:
    od = (brand.official_domain or "").lower().replace("https://", "").replace("http://", "").strip("/")
    return bool(od) and (url_domain == od or url_domain.endswith("." + od))


# SOV 失真防护：引用总数太少时 SOV 没有意义（1 条引用全为自己 → 100% 是假象）
MIN_CITATIONS_FOR_SOV = 5


def brand_visibility(db: Session, brand_id: int, since: datetime | None = None) -> dict:
    """品牌 AI 可见度总览。"""
    brand = db.get(Brand, brand_id)
    if brand is None:
        return {"error": "brand 不存在"}
    since = since or (datetime.utcnow() - timedelta(days=7))

    latest = _latest_response_by_keyword(db, brand_id)
    responses = list(latest.values())
    resp_ids = [r.id for r in responses]

    total_queries = len(responses)
    mentioned_queries = 0
    for r in responses:
        if db.query(BrandMention).filter(BrandMention.response_id == r.id, BrandMention.brand_id == brand_id).first():
            mentioned_queries += 1

    # 按引擎拆分的可见度（跨引擎对比：同一品牌在每家 AI 的说法往往不同）
    engine_stats: dict[str, dict] = {}
    for r in responses:
        st = engine_stats.setdefault(r.engine, {"total_queries": 0, "mentioned_queries": 0})
        st["total_queries"] += 1
        if db.query(BrandMention).filter(BrandMention.response_id == r.id, BrandMention.brand_id == brand_id).first():
            st["mentioned_queries"] += 1
    engine_breakdown = [
        {
            "engine": eng,
            "total_queries": s["total_queries"],
            "mentioned_queries": s["mentioned_queries"],
            "visibility_rate": round(s["mentioned_queries"] / s["total_queries"], 4) if s["total_queries"] else 0.0,
        }
        for eng, s in sorted(engine_stats.items())
    ]

    # 引用统计
    citations: list[Citation] = []
    if resp_ids:
        citations = db.query(Citation).filter(Citation.response_id.in_(resp_ids)).all()
    own_citations = [c for c in citations if _domain_matches(c.domain, brand)]
    total_citations = len(citations)

    negative = db.query(BrandMention).filter(
        BrandMention.brand_id == brand_id,
        BrandMention.sentiment == "negative",
        BrandMention.response_id.in_(resp_ids),
    ).count() if resp_ids else 0

    top_domains = Counter(c.domain for c in citations).most_common(5)

    # SOV 失真防护：引用总数 < 阈值时返回 None，避免"1 条自引用 = 100%"假象
    sov = round(len(own_citations) / total_citations, 4) if total_citations else 0.0
    sov_insufficient = total_citations < MIN_CITATIONS_FOR_SOV
    if sov_insufficient and total_citations:
        sov = None

    return {
        "brand_id": brand_id,
        "brand_name": brand.name,
        "period_since": since.isoformat(),
        "total_queries": total_queries,
        "mentioned_queries": mentioned_queries,
        "visibility_rate": round(mentioned_queries / total_queries, 4) if total_queries else 0.0,
        "total_citations": total_citations,
        "own_citations": len(own_citations),
        "sov": sov,
        "sov_insufficient": sov_insufficient,
        "negative_mentions": negative,
        "top_cited_domains": [{"domain": d, "count": c} for d, c in top_domains],
        "engine_breakdown": engine_breakdown,
    }


def compare_brands(db: Session, brand_ids: list[int]) -> list[dict]:
    """竞品对比：多个品牌同一口径的可见度/引用/负面并列（GEO 客户最关心的"谁在 AI 里更可见"）。"""
    out = []
    for bid in brand_ids:
        vis = brand_visibility(db, bid)
        if "error" in vis:
            continue
        out.append({
            "brand_id": bid,
            "brand_name": vis["brand_name"],
            "visibility_rate": vis["visibility_rate"],
            "mentioned_queries": vis["mentioned_queries"],
            "total_queries": vis["total_queries"],
            "sov": vis["sov"],
            "sov_insufficient": vis["sov_insufficient"],
            "total_citations": vis["total_citations"],
            "negative_mentions": vis["negative_mentions"],
            "engine_breakdown": vis["engine_breakdown"],
        })
    return out


def answer_gaps(db: Session, brand_id: int) -> list[dict]:
    """答案缺口：竞品被 AI 提及而你缺席的 query 清单（服务交付的核心抓手）。

    判定规则：该 query 的最新回答中，竞品名/别名出现在正文、或竞品官网域名出现在引用里，
    而本品牌两者都未出现 → 记为缺口。
    """
    brand = db.get(Brand, brand_id)
    if brand is None:
        return []
    competitors = [db.get(Brand, cid) for cid in (brand.competitor_ids or [])]
    competitors = [c for c in competitors if c is not None]

    own_names = _brand_names(brand)
    gaps: list[dict] = []
    latest = _latest_response_by_keyword(db, brand_id)

    for kw_id, resp in latest.items():
        kw = db.get(Keyword, kw_id)
        text_lower = resp.response_text.lower()

        own_present = any(n in text_lower for n in own_names)
        if not own_present:
            own_domains = [c.domain for c in db.query(Citation).filter(Citation.response_id == resp.id).all()]
            if any(_domain_matches(d, brand) for d in own_domains):
                own_present = True

        present_competitors = []
        for comp in competitors:
            comp_present = any(n in text_lower for n in _brand_names(comp))
            if not comp_present:
                comp_domains = [c.domain for c in db.query(Citation).filter(Citation.response_id == resp.id).all()]
                if any(_domain_matches(d, comp) for d in comp_domains):
                    comp_present = True
            if comp_present:
                present_competitors.append(comp.name)

        if present_competitors and not own_present:
            gaps.append({
                "keyword_id": kw_id,
                "query_text": kw.query_text if kw else "",
                "scenario": kw.scenario if kw else "",
                "engine": resp.engine,
                "competitors_present": present_competitors,
                "response_id": resp.id,
                "snippet": resp.response_text[:200],
            })

    return gaps


def answer_gaps_by_engine(db: Session, brand_id: int) -> dict:
    """答案缺口按引擎分组：{engine: {"count": n, "gaps": [...]}}。"""
    gaps = answer_gaps(db, brand_id)
    result: dict[str, dict] = {}
    for g in gaps:
        eng = g.get("engine", "unknown")
        entry = result.setdefault(eng, {"count": 0, "gaps": []})
        entry["count"] += 1
        entry["gaps"].append(g)
    return result


def content_citations(db: Session, brand_id: int, hours: int | None = None) -> dict:
    """自媒体/RAG 内容引用追踪：品牌配置的 monitored_urls 被 AI 引用的明细。

    RAG 场景说明：AI 回答引用某 URL = 该内容进入了检索索引并被采纳，
    对自媒体客户来说就是"我的内容被 AI 引用了几次、在哪些问题里、哪些引擎"。
    """
    brand = db.get(Brand, brand_id)
    if brand is None:
        return {"error": "brand 不存在"}
    monitored = [u.strip() for u in (brand.monitored_urls or []) if u and u.strip()]
    if not monitored:
        return {"monitored_urls": [], "total": 0, "items": []}

    q = db.query(Citation, AIResponse).join(AIResponse, Citation.response_id == AIResponse.id)
    if hours:
        since = datetime.utcnow() - timedelta(hours=hours)
        q = q.filter(AIResponse.sampled_at >= since)

    def norm(u: str) -> str:
        u = u.split("#")[0].split("?")[0].rstrip("/")
        return u.lower()

    monitored_norm = {norm(u): u for u in monitored}
    # 同时支持按域名匹配（如监控整站内容）
    from urllib.parse import urlparse
    monitored_domains = {urlparse(u).netloc.lower() for u in monitored if urlparse(u).netloc}

    items: dict[str, dict] = {}
    for cit, resp in q.all():
        key = norm(cit.url)
        matched = monitored_norm.get(key)
        if matched is None:
            d = cit.domain.lower()
            if not (monitored_domains and (d in monitored_domains or any(d.endswith("." + md) for md in monitored_domains))):
                continue
            matched = cit.url
        entry = items.setdefault(matched, {"url": matched, "count": 0, "queries": [], "engines": set()})
        entry["count"] += 1
        if resp.prompt_text not in entry["queries"]:
            entry["queries"].append(resp.prompt_text)
        entry["engines"].add(resp.engine)

    out = []
    for it in items.values():
        out.append({
            "url": it["url"],
            "count": it["count"],
            "queries": it["queries"][:10],
            "engines": sorted(it["engines"]),
        })
    out.sort(key=lambda x: -x["count"])
    return {
        "monitored_urls": monitored,
        "total": sum(x["count"] for x in out),
        "items": out,
    }


def recent_negative_mentions(db: Session, brand_id: int, hours: int = 24) -> list[dict]:
    """近 N 小时负面提及明细（用于告警）。"""
    since = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(BrandMention, AIResponse)
        .join(AIResponse, BrandMention.response_id == AIResponse.id)
        .filter(
            BrandMention.brand_id == brand_id,
            BrandMention.sentiment == "negative",
            AIResponse.sampled_at >= since,
        )
        .order_by(AIResponse.sampled_at.desc())
        .all()
    )
    return [
        {
            "mention_id": m.id,
            "response_id": m.response_id,
            "context": m.context,
            "query": r.prompt_text,
            "engine": r.engine,
            "sampled_at": r.sampled_at.isoformat(),
        }
        for m, r in rows
    ]
