"""跨引擎对比 HTML 报告生成器。

产出：reports/<品牌名>/GEO跨引擎对比报告_<日期>.html
自包含单页（内联 CSS + ECharts CDN），直接在浏览器打开，用于给客户看：
各引擎可见度 / SOV / 答案缺口 / 引用域名 / 内容引用（自媒体 RAG）对比。

用法（项目根目录）：
    python scripts/gen_report.py 2          # 生成品牌 2 的 HTML 对比报告
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import Brand
from app.services import metrics

# 生成 HTML 前的数据组装（供 API / 脚本复用）
def build_report_data(db: Session, brand_id: int, days: int = 7) -> dict:
    brand = db.get(Brand, brand_id)
    if brand is None:
        raise ValueError(f"brand {brand_id} 不存在")
    period_end = datetime.utcnow()
    period_start = period_end - timedelta(days=days)
    vis = metrics.brand_visibility(db, brand_id, since=period_start)
    gaps_by_engine = metrics.answer_gaps_by_engine(db, brand_id)
    cc = metrics.content_citations(db, brand_id)
    from app.services import content as content_svc
    authority = content_svc.authority_score(db, brand_id)
    gap_flat = metrics.answer_gaps(db, brand_id)
    themes = [{"query": g["query_text"], "content_type": content_svc._scenario_type(g.get("scenario", ""))}
              for g in gap_flat[:8]]
    return {
        "brand": brand,
        "period_start": period_start.date().isoformat(),
        "period_end": period_end.date().isoformat(),
        "vis": vis,
        "gaps_by_engine": gaps_by_engine,
        "content": cc,
        "authority": authority,
        "themes": themes,
    }


def render_html(data: dict) -> str:
    brand = data["brand"]
    vis = data["vis"]
    eb = vis.get("engine_breakdown", [])
    gaps_by_engine = data["gaps_by_engine"]
    cc = data["content"]

    # 引擎可见度/缺口序列（保持引擎顺序）
    engines_sorted = sorted({e["engine"] for e in eb} | set(gaps_by_engine.keys()))
    vis_series = [next((e["visibility_rate"] * 100 for e in eb if e["engine"] == eng), 0) for eng in engines_sorted]
    gap_series = [gaps_by_engine.get(eng, {}).get("count", 0) for eng in engines_sorted]

    def chart_block(series: list, all_zero: bool) -> str:
        if all_zero or not engines_sorted:
            return '<div class="chart-empty">本期暂无数据（请确认采样任务已运行）</div>'
        return '<div class="chart" id="chart_%s"></div>' % ("vis" if series is vis_series else "gap")

    vis_chart = chart_block(vis_series, all(not v for v in vis_series))
    gap_chart = chart_block(gap_series, all(not g for g in gap_series))

    chart_payload = json.dumps({
        "engines": engines_sorted,
        "vis": vis_series,
        "gaps": gap_series,
    }, ensure_ascii=False)

    kpi = [
        ("AI 可见度", f"{vis.get('visibility_rate', 0) * 100:.1f}%", "所有引擎中品牌被提及的查询占比"),
        ("引用份额 SOV",
         "数据不足" if vis.get("sov") is None else f"{vis['sov'] * 100:.1f}%",
         "自身域名引用 / 全部引用（引用 <5 条时为数据不足）"),
        ("引用总数", str(vis.get("total_citations", 0)), "AI 回答中的引用链接"),
        ("负面提及", str(vis.get("negative_mentions", 0)), "近 7 天回答中的负面语境"),
    ]
    kpi_html = "".join(
        f'<div class="kpi"><div class="kpi-v">{v}</div><div class="kpi-l">{k}</div><div class="kpi-d">{d}</div></div>'
        for k, v, d in kpi
    )

    # 各引擎可见度表
    eng_rows = "".join(
        f"<tr><td>{e['engine']}</td><td>{e['total_queries']}</td><td>{e['mentioned_queries']}</td>"
        f"<td>{e['visibility_rate'] * 100:.1f}%</td></tr>"
        for e in sorted(eb, key=lambda x: x["engine"])
    ) or '<tr><td colspan="4" class="empty">暂无采样数据</td></tr>'

    # 缺口表
    gap_rows = ""
    if gaps_by_engine:
        for eng, entry in sorted(gaps_by_engine.items()):
            qs = "、".join(g["query_text"] for g in entry["gaps"][:3])
            gap_rows += f"<tr><td>{eng}</td><td>{entry['count']}</td><td>{qs}</td></tr>"
    else:
        gap_rows = '<tr><td colspan="3" class="empty">暂无缺口（竞品没有出现在你的缺席位置）</td></tr>'

    # 引用域名表
    dom_rows = "".join(
        f"<tr><td>{d['domain']}</td><td>{d['count']}</td></tr>"
        for d in vis.get("top_cited_domains", [])
    ) or '<tr><td colspan="2" class="empty">暂无引用</td></tr>'

    # 内容引用（自媒体 RAG）
    content_block = ""
    monitored = cc.get("monitored_urls") or []
    if monitored:
        if cc.get("items"):
            items_rows = "".join(
                f"<tr><td>{it['url']}</td><td>{it['count']}</td><td>{it['queries'][0][:50]}</td>"
                f"<td>{', '.join(it['engines'])}</td></tr>"
                for it in cc["items"][:10]
            )
            content_block = (
                f'<div class="card"><h2>内容引用追踪（自媒体 / RAG）</h2>'
                f'<p class="hint">监控 {len(monitored)} 条内容，共被 AI 引用 <b>{cc["total"]}</b> 次'
                f'——引用 = 内容进入了 AI 检索（RAG）并被采纳。</p>'
                f'<div class="tbl-wrap"><table class="fixed"><colgroup><col style="width:38%"><col style="width:10%">'
                f'<col style="width:32%"><col style="width:20%"></colgroup>'
                f'<thead><tr><th>内容 URL</th><th>引用次数</th><th>出现的问题</th><th>引擎</th></tr></thead>'
                f'<tbody>{items_rows}</tbody></table></div></div>'
            )
        else:
            content_block = (
                f'<div class="card"><h2>内容引用追踪（自媒体 / RAG）</h2>'
                f'<p class="hint">已监控 {len(monitored)} 条内容，本期未被 AI 引用——内容可能还没被检索收录，'
                f'或需要优化内容结构（见缺口与建议）。</p></div>'
            )
    else:
        content_block = (
            '<div class="card"><h2>内容引用追踪（自媒体 / RAG）</h2>'
            '<p class="hint">该客户未配置内容监控 URL。自媒体客户建议在创建品牌时填写 '
            '<code>monitored_urls</code>（公众号文章 / 小红书 / B站链接），即可追踪内容被 AI 引用的次数与场景。</p></div>'
        )

    # 内容优化动作（AI-ready 生成 + 权威度建设）
    au = data["authority"]
    theme_rows = ""
    if data["themes"]:
        theme_rows = "".join(
            f"<tr><td>{t['query']}</td><td>{t['content_type']}</td></tr>" for t in data["themes"]
        )
    else:
        theme_rows = '<tr><td colspan="2" class="empty">暂无缺口主题（可先覆盖品类词或新品主题）</td></tr>'
    opt_block = (
        f'<div class="card"><h2>内容优化动作（AI-ready 生成 / 权威度）</h2>'
        f'<p class="hint">缺口主题优先写作；权威域引用 {au["authority_citations"]}/{au["total_citations"]}'
        f'（{au["authority_ratio"] * 100:.1f}%）——发布时带上结构化标记（llms.txt / FAQPage Schema）更容易被 AI 采纳。</p>'
        f'<div class="tbl-wrap"><table class="fixed"><colgroup><col style="width:62%"><col style="width:38%"></colgroup>'
        f'<thead><tr><th>缺口主题（内容选题）</th><th>建议内容类型</th></tr></thead>'
        f'<tbody>{theme_rows}</tbody></table></div>'
        f'<p class="hint">完整动作清单（FAQ 候选、llms.txt 模板、FAQPage Schema、索引检查步骤）见 '
        f'<code>python scripts/gen_brief.py {data["brand"].id}</code> 生成的 Brief。</p></div>'
    )

    return _TEMPLATE.replace("__KPI__", kpi_html).replace("__ENG_ROWS__", eng_rows) \
        .replace("__GAP_ROWS__", gap_rows).replace("__DOM_ROWS__", dom_rows) \
        .replace("__CONTENT_BLOCK__", content_block).replace("__OPT_BLOCK__", opt_block) \
        .replace("__VIS_CHART__", vis_chart).replace("__GAP_CHART__", gap_chart) \
        .replace("__BRAND__", brand.name) \
        .replace("__PERIOD__", f"{data['period_start']} ~ {data['period_end']}") \
        .replace("__CHART__", chart_payload)


def generate_engine_report(db: Session, brand_id: int, days: int = 7) -> dict:
    data = build_report_data(db, brand_id, days)
    html = render_html(data)
    out_dir = os.path.join("reports", f"{data['brand'].name}")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"GEO跨引擎对比报告_{data['period_end']}.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return {"path": path, "brand": data["brand"].name}


_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__BRAND__ GEO 跨引擎对比报告</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Ccircle cx='32' cy='32' r='28' fill='%231d4ed8'/%3E%3Ctext x='32' y='42' font-size='30' text-anchor='middle' fill='white' font-family='Arial'%3EG%3C/text%3E%3C/svg%3E">
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif; background: #f5f7fa; color: #1f2937; line-height: 1.6; }
  .wrap { max-width: 1100px; margin: 0 auto; padding: 24px 16px 48px; }
  .head { display: flex; flex-wrap: wrap; gap: 12px; align-items: flex-end; justify-content: space-between; margin-bottom: 20px; }
  .head h1 { font-size: 26px; font-weight: 700; letter-spacing: .5px; }
  .head .meta { color: #6b7280; font-size: 13.5px; }
  .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px; }
  .kpi { background: #fff; border-radius: 12px; padding: 16px; border: 1px solid #e5e7eb; }
  .kpi-v { font-size: 26px; font-weight: 800; color: #1d4ed8; }
  .kpi-l { font-size: 14px; font-weight: 600; margin-top: 4px; }
  .kpi-d { font-size: 12.5px; color: #6b7280; margin-top: 2px; }
  .grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 12px; }
  .card { background: #fff; border-radius: 12px; padding: 18px; border: 1px solid #e5e7eb; margin-bottom: 12px; }
  .card h2 { font-size: 16px; font-weight: 700; margin-bottom: 10px; }
  .hint { font-size: 13px; color: #6b7280; margin-bottom: 10px; }
  .chart { width: 100%; height: 300px; }
  .chart-empty { width: 100%; height: 300px; display: flex; align-items: center; justify-content: center; color: #9ca3af; font-size: 14px; }
  .tbl-wrap { overflow-x: auto; }
  table.fixed { table-layout: fixed; width: 100%; border-collapse: collapse; font-size: 14px; }
  table.fixed th, table.fixed td { padding: 9px 10px; text-align: left; border-bottom: 1px solid #eef0f3; word-break: break-all; }
  table.fixed th { background: #f8fafc; font-weight: 600; color: #374151; }
  td.empty { color: #9ca3af; text-align: center; }
  code { background: #f1f5f9; padding: 1px 5px; border-radius: 4px; font-size: 12.5px; }
  .note { font-size: 12.5px; color: #9ca3af; margin-top: 18px; }
  @media (max-width: 800px) {
    .kpis { grid-template-columns: repeat(2, 1fr); }
    .grid2 { grid-template-columns: 1fr; }
    .head { flex-direction: column; align-items: flex-start; }
  }
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <div><h1>__BRAND__ · GEO 跨引擎对比报告</h1>
      <div class="meta">数据期间：__PERIOD__ ｜ 数据来自各 AI 引擎网页版真实采样</div>
    </div>
  </div>

  <div class="kpis">__KPI__</div>

  <div class="grid2">
    <div class="card"><h2>各引擎 AI 可见度</h2><p class="hint">同一品牌、同一批问题，各家 AI 提到你的比例</p>
      __VIS_CHART__</div>
    <div class="card"><h2>各引擎答案缺口</h2><p class="hint">竞品出现而本品牌缺席的查询数量</p>
      __GAP_CHART__</div>
  </div>

  <div class="card"><h2>各引擎可见度明细</h2>
    <div class="tbl-wrap"><table class="fixed"><colgroup><col style="width:20%"><col style="width:20%"><col style="width:20%"><col style="width:40%"></colgroup>
    <thead><tr><th>引擎</th><th>监控查询</th><th>被提及</th><th>可见度</th></tr></thead>
    <tbody>__ENG_ROWS__</tbody></table></div></div>

  <div class="card"><h2>答案缺口（按引擎）</h2>
    <div class="tbl-wrap"><table class="fixed"><colgroup><col style="width:18%"><col style="width:12%"><col style="width:70%"></colgroup>
    <thead><tr><th>引擎</th><th>缺口数</th><th>涉及查询</th></tr></thead>
    <tbody>__GAP_ROWS__</tbody></table></div></div>

  <div class="card"><h2>被引用 Top 域名</h2><p class="hint">AI 在回答相关问题时引用了哪些网站——这是内容布局的切入点</p>
    <div class="tbl-wrap"><table class="fixed"><colgroup><col style="width:70%"><col style="width:30%"></colgroup>
    <thead><tr><th>域名</th><th>引用次数</th></tr></thead>
    <tbody>__DOM_ROWS__</tbody></table></div></div>

  __CONTENT_BLOCK__

  __OPT_BLOCK__

  <div class="note">本报告由 GEO Studio 自动生成。数据为采样时点的真实回答，AI 回答具有时效性与波动性；"可见度"=品牌被提及的查询占比，与品牌词是否进入 AI 检索采纳直接相关。</div>
</div>
<script>
(function () {
  var D = __CHART__;
  function bar(el, series, name, color) {
    var c = echarts.init(document.getElementById(el));
    c.setOption({
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      grid: { left: 40, right: 20, top: 20, bottom: 30 },
      xAxis: { type: 'category', data: D.engines, axisLabel: { fontSize: 12 } },
      yAxis: { type: 'value', minInterval: 1, axisLabel: { fontSize: 11 } },
      series: [{ name: name, type: 'bar', data: series, itemStyle: { color: color, borderRadius: [4, 4, 0, 0] }, barMaxWidth: 46 }]
    });
    window.addEventListener('resize', function () { c.resize(); });
  }
  try { bar('chart_vis', D.vis, '可见度 %', '#1d4ed8'); } catch (e) {}
  try { bar('chart_gap', D.gaps, '缺口数', '#dc2626'); } catch (e) {}
})();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.database import SessionLocal
    brand_id = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    db = SessionLocal()
    try:
        r = generate_engine_report(db, brand_id)
        print(r["path"])
    finally:
        db.close()
