"""周报生成：每客户一页 Markdown，落到 reports/ 目录，同时存 reports 表。

MVP 阶段周报是你服务交付的载体：可见度、SOV、负面提及、答案缺口、
被引用 Top 域名 + 下一步建议（占位，人工填写）。
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Brand, Report
from app.services import metrics
from app.services.snapshot import last_two_visibility


def _fmt(v: float) -> str:
    return f"{v * 100:.1f}%"


def generate_weekly_report(db: Session, brand_id: int, days: int = 7) -> dict:
    brand = db.get(Brand, brand_id)
    if brand is None:
        return {"error": "brand 不存在"}

    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)
    vis = metrics.brand_visibility(db, brand_id, since=period_start)
    gaps = metrics.answer_gaps(db, brand_id)
    negatives = metrics.recent_negative_mentions(db, brand_id, hours=days * 24)

    lines = [
        f"# {brand.name} GEO 周报",
        "",
        f"期间：{period_start.date()} ~ {period_end.date()}",
        "",
        "## 核心指标",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| 监控查询数 | {vis.get('total_queries', 0)} |",
        f"| 被提及查询数 | {vis.get('mentioned_queries', 0)} |",
        f"| AI 可见度 | {_fmt(vis.get('visibility_rate', 0))} |",
        f"| 引用总数 | {vis.get('total_citations', 0)} |",
        f"| 自身域名引用 | {vis.get('own_citations', 0)} |",
        f"| 引用份额 SOV | {'数据不足（引用 <5 条）' if vis.get('sov') is None else _fmt(vis['sov'])} |",
        f"| 负面提及 | {vis.get('negative_mentions', 0)} |",
    ]
    # 环比：对比最近两次采样快照的可见度
    prev_v, curr_v = last_two_visibility(db, brand_id)
    if prev_v is not None and curr_v is not None:
        diff = curr_v - prev_v
        arrow = "▲" if diff >= 0 else "▼"
        lines.append(f"| 可见度环比（上期 {_fmt(prev_v)}） | {arrow} {_fmt(abs(diff))} |")
    else:
        lines.append("| 可见度环比 | 数据不足（需至少两轮采样） |")
    lines += [
        "",
        "## 各引擎可见度（跨引擎对比）",
        "",
        "| 引擎 | 监控查询 | 被提及 | 可见度 |",
        "| --- | --- | --- | --- |",
    ]
    for e in vis.get("engine_breakdown", []):
        lines.append(
            f"| {e['engine']} | {e['total_queries']} | {e['mentioned_queries']} | {_fmt(e['visibility_rate'])} |"
        )
    lines += [
        "",
        "## 答案缺口（竞品在、你不在的查询）",
        "",
    ]
    gaps_by_engine = metrics.answer_gaps_by_engine(db, brand_id)
    if gaps_by_engine:
        lines.append("| 引擎 | 缺口数 | 涉及查询 |")
        lines.append("| --- | --- | --- |")
        for eng, entry in sorted(gaps_by_engine.items()):
            qs = "、".join(g["query_text"] for g in entry["gaps"][:3])
            lines.append(f"| {eng} | {entry['count']} | {qs} |")
        lines.append("")
    if gaps:
        for g in gaps[:20]:
            lines.append(
                f"- **{g['query_text']}**（{g['scenario']} / {g['engine']}）"
                f"｜竞品：{', '.join(g['competitors_present'])}"
            )
            lines.append(f"  - AI 回答摘录：{g['snippet'][:120]}...")
    else:
        lines.append("（暂无缺口）")

    lines += ["", "## 内容引用追踪（自媒体/RAG 监控）", ""]
    cc = metrics.content_citations(db, brand_id)
    if cc.get("monitored_urls"):
        if cc.get("items"):
            lines.append(f"监控内容共被引用 **{cc['total']}** 次：")
            lines.append("")
            lines.append("| 内容 URL | 被引用次数 | 出现的问题 | 引擎 |")
            lines.append("| --- | --- | --- | --- |")
            for it in cc["items"][:10]:
                lines.append(
                    f"| {it['url'][:60]} | {it['count']} | {it['queries'][0][:40]} | {', '.join(it['engines'])} |"
                )
        else:
            lines.append(f"已监控 {len(cc['monitored_urls'])} 条内容，本期未被 AI 引用")
    else:
        lines.append("（该客户未配置内容监控 URL，如需追踪发布内容引用，创建品牌时填 monitored_urls）")

    lines += ["", "## 负面提及明细", ""]
    if negatives:
        for n in negatives[:20]:
            lines.append(f"- [{n['engine']}] {n['query']}：{n['context'][:100]}")
    else:
        lines.append("（无）")

    lines += ["", "## 被引用 Top 域名", ""]
    lines.append("| 域名 | 次数 |")
    lines.append("| --- | --- |")
    for d in vis.get("top_cited_domains", []):
        lines.append(f"| {d['domain']} | {d['count']} |")

    lines += ["", "## 下一步建议", "", "- （人工填写：本周优化的内容与下周转化的动作）", ""]

    # 内容优化建议（GEO 第三层：基于缺口数据生成动作清单）
    from app.services.content import generate_brief
    brief = generate_brief(db, brand_id)
    if "error" not in brief:
        lines += ["", "## 内容优化建议（AI-ready 内容生成）", ""]
        if brief["themes"]:
            lines.append("本周缺口主题（写内容优先选这些）：")
            lines.append("")
            lines.append("| 主题查询 | 建议内容类型 |")
            lines.append("| --- | --- |")
            for t in brief["themes"][:5]:
                lines.append(f"| {t['query']} | {t['content_type']} |")
        lines += ["", f"- FAQ 候选 {len(brief['faqs'])} 条，已生成 FAQPage Schema 模板（见 Brief）",
                  f"- 权威域引用 {brief['authority']['authority_citations']}/{brief['authority']['total_citations']}"
                  f"（{brief['authority']['authority_ratio'] * 100:.1f}%）",
                  f"- 完整 Brief（含 llms.txt / Schema / 索引检查清单）：`{brief.get('path', '')}`", ""]

    content_md = "\n".join(lines)

    # 存库
    report = Report(
        brand_id=brand_id,
        period_start=period_start,
        period_end=period_end,
        metrics_json=vis,
        content_md=content_md,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    # 落盘
    out_dir = os.path.join("reports", f"{brand.name}")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"GEO周报_{period_start.date()}_{period_end.date()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content_md)

    return {"report_id": report.id, "path": path, "content": content_md}


def generate_account_report(db: Session, brand_id: int, days: int = 7) -> dict:
    """账号 GEO 周报：内容被引率 / 内容级 RAG 归因（哪篇哪句话）/ 收录时效 / 跨平台归因。"""
    from app.services import account as account_svc

    brand = db.get(Brand, brand_id)
    if brand is None:
        return {"error": "brand 不存在"}
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)
    s = account_svc.account_summary(db, brand_id, hours=days * 24)
    if "error" in s:
        return {"error": s["error"]}

    lines = [
        f"# {brand.name} 账号 GEO 周报（内容被 AI 引用监测）",
        "",
        f"期间：{period_start.date()} ~ {period_end.date()}",
        "",
        "## 核心指标（账号视角）",
        "",
        "| 指标 | 数值 |",
        "| --- | --- |",
        f"| 监控内容数 | {s['content_count']} |",
        f"| 被引用内容数 | {s['cited_content_count']} |",
        f"| 内容被引率 | {_fmt(s['citation_rate'])} |",
        f"| 引用总次数 | {s['total_citations']} |",
        f"| 平均收录时效 | {s.get('avg_cited_duration') or '-'} |",
        "",
        "## 跨平台发布效果归因",
        "",
        "| 平台 | 内容数 | 被引内容 | 内容被引率 | 引用次数 | 平均收录时效 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if s["platforms"]:
        for p in s["platforms"]:
            lines.append(
                f"| {p['platform']} | {p['content_count']} | {p['cited_count']} | "
                f"{_fmt(p['citation_rate'])} | {p['citations']} | {p.get('avg_duration') or '-'} |"
            )
    else:
        lines.append("（无平台数据）")

    lines += ["", "## 内容被引 Top（内容级 RAG 归因）", ""]
    if s["items"]:
        lines.append("| 内容 | 平台 | 被引次数 | 发布时间 | 首次收录 | 收录时效 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for it in s["items"][:10]:
            lines.append(
                f"| {it['url'][:50]} | {it['platform']} | {it['citation_count']} | "
                f"{(it['published_at'] or '-')[:10]} | {(it['first_cited_at'] or '-')[:10]} | {it['duration']} |"
            )
        lines += ["", "### 引用明细（AI 在哪些问题里引用了你的哪句话）", ""]
        for it in s["items"][:5]:
            lines.append(f"- **{it['url'][:50]}**（{it['citation_count']} 次引用）")
            for c in it["citations"][:3]:
                snippet = (c["snippet"] or "")[:90]
                lines.append(f"  - [{c['engine']}] 问「{c['query'][:40]}」→ 引用原文：{snippet}")
    else:
        lines.append("（暂无内容被 AI 引用）")

    lines += ["", "## 未收录内容（发布后尚未被 AI 引用）", ""]
    if s["uncited"]:
        for u in s["uncited"][:10]:
            pa = (u["published_at"] or "未知")[:10]
            lines.append(f"- {u['url'][:60]}（平台：{u['platform']}，发布时间：{pa}）")
    else:
        lines.append("（全部监控内容均已被引用）")

    lines += ["", "## 同领域账号对比（内容被引维度）", ""]
    if s["compare"]:
        lines.append("| 账号 | 内容数 | 被引内容 | 内容被引率 | 引用次数 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for c in s["compare"]:
            lines.append(
                f"| {c['brand_name']} | {c['content_count']} | {c['cited_content_count']} | "
                f"{_fmt(c['citation_rate'])} | {c['total_citations']} |"
            )
    lines += ["", "## 下一步建议（自媒体客户）", "",
              "- 发布新内容后及时登记到控制台「内容清单」（填发布时间），系统自动监测收录时效；",
              "- 被引用 Top 内容 = 已验证的选题方向，按相同主题/结构扩大生产；",
              "- 未收录内容：优化标题/摘要/结构（FAQ、Schema、llms.txt），参考内容优化 Brief。", ""]

    content_md = "\n".join(lines)
    report = Report(
        brand_id=brand_id,
        period_start=period_start,
        period_end=period_end,
        metrics_json={"account": s},
        content_md=content_md,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    out_dir = os.path.join("reports", brand.name)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"账号GEO周报_{period_start.date()}_{period_end.date()}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content_md)
    return {"report_id": report.id, "path": path, "content": content_md}
