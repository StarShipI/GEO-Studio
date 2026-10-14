# -*- coding: utf-8 -*-
"""可见度历史快照：每轮采样完成后为涉及品牌写一行，支撑趋势与环比。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Brand, Snapshot
from app.services import metrics


def write_brand_snapshot(db: Session, brand_id: int, engine: str = "") -> Snapshot:
    """为品牌当前最新指标写一行快照（engine="" 表示全引擎汇总）。"""
    vis = metrics.brand_visibility(db, brand_id)
    if "error" in vis:
        return None
    snap = Snapshot(
        brand_id=brand_id,
        engine=engine,
        total_queries=vis["total_queries"],
        mentioned_queries=vis["mentioned_queries"],
        visibility_rate=vis["visibility_rate"],
        total_citations=vis["total_citations"],
        own_citations=vis["own_citations"],
        sov=vis["sov"],
        negative_mentions=vis["negative_mentions"],
    )
    db.add(snap)
    db.commit()
    return snap


def write_snapshots_for_brands(db: Session, brand_ids: list[int]) -> int:
    """对一组品牌各写一行全引擎汇总快照（采样轮结束后调用）。"""
    n = 0
    for bid in set(brand_ids):
        if db.get(Brand, bid) is not None and write_brand_snapshot(db, bid) is not None:
            n += 1
    return n


def brand_trend(db: Session, brand_id: int, limit: int = 30) -> list[dict]:
    """品牌可见度趋势（按时间倒序取最近 limit 行汇总快照）。"""
    rows = (
        db.query(Snapshot)
        .filter(Snapshot.brand_id == brand_id, Snapshot.engine == "")
        .order_by(Snapshot.sampled_at.desc())
        .limit(limit)
        .all()
    )
    out = []
    for s in reversed(rows):
        out.append({
            "sampled_at": s.sampled_at.isoformat(),
            "total_queries": s.total_queries,
            "mentioned_queries": s.mentioned_queries,
            "visibility_rate": s.visibility_rate,
            "total_citations": s.total_citations,
            "own_citations": s.own_citations,
            "sov": s.sov,
            "negative_mentions": s.negative_mentions,
        })
    return out


def last_two_visibility(db: Session, brand_id: int) -> tuple[float | None, float | None]:
    """最近两次汇总快照的可见度（用于周报环比），不足两条返回 (None, None)。"""
    rows = (
        db.query(Snapshot)
        .filter(Snapshot.brand_id == brand_id, Snapshot.engine == "")
        .order_by(Snapshot.sampled_at.desc())
        .limit(2)
        .all()
    )
    if len(rows) < 2:
        return None, None
    return rows[1].visibility_rate, rows[0].visibility_rate
