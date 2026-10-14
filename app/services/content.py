"""内容优化工作台：把"洞察"转化为"动作"（GEO 四层架构的第三层）。

四件套：
1. AI-ready 内容生成 —— generate_brief()：基于答案缺口生成文章/榜单/Brief（含 FAQ 候选）；
2. 结构化 —— structure_templates()：llms.txt 模板、FAQPage Schema JSON-LD、论证结构模板；
3. 权威度建设 —— authority_score()：高权重域名（百科/行业站/内容平台）对品牌的引用统计 + 动作清单；
4. 索引保障 —— check_index()：对品牌发布的内容 URL 向 AI 引擎提问验证是否已收录（RAG 索引检查）。

设计原则：全部基于库里已有的真实数据（缺口/引用/可见度）生成，不做空想建议。
"""
from __future__ import annotations

import os
from datetime import datetime
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import Brand
from app.services import metrics

# 权威度建设：默认高权重域名清单（AI 更倾向采信/引用这些域名的内容）
AUTHORITY_DOMAINS = [
    "zh.wikipedia.org",        # 维基百科
    "baike.baidu.com",         # 百度百科
    "zhihu.com",               # 知乎（高权重 UGC）
    "xiaohongshu.com",         # 小红书
    "mp.weixin.qq.com",        # 微信公众号
    "bilibili.com",            # B 站
    "douyin.com",              # 抖音
    "36kr.com",                # 36氪（行业媒体）
    "huxiu.com",               # 虎嗅
    "www.gov.cn",              # 政府/权威机构
    "ndrc.gov.cn",             # 发改委
    "moe.gov.cn",              # 教育部
]

# 内容类型与场景映射：缺口查询该写成什么内容
SCENARIO_TO_CONTENT_TYPE = {
    "是什么": "知识型文章（定义/背景/发展，配结构化小标题）",
    "怎么样": "评测体验文（真实体验 + 分维度评价）",
    "值得推荐吗": "推荐榜（推荐理由+适用人群清单式）",
    "价格怎么样": "价格解读文（价格区间/版本/性价比对比）",
    "和竞品比怎么样": "对比评测（同维度打分表 + 结论）",
    "品类推荐": "品类榜单（Top N 推荐 + 选购理由）",
}


def _scenario_type(scenario: str) -> str:
    return SCENARIO_TO_CONTENT_TYPE.get(scenario, "图文文章（清晰论证结构）")


def _domain_of(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower()
    except Exception:
        return ""


def _is_authority(domain: str, brand: Brand) -> bool:
    """域名是否命中权威清单（含子域，如 zhuanlan.zhihu.com 命中 zhihu.com）。"""
    ad = list(AUTHORITY_DOMAINS) + [d.strip().lower() for d in (brand.aliases or []) if "." in d]
    for a in ad:
        a = a.lower().lstrip(".")
        if domain == a or domain.endswith("." + a):
            return True
    return False


# ---------- 1. AI-ready 内容生成 ----------

def generate_brief(db: Session, brand_id: int) -> dict:
    """基于答案缺口 + 引用格局生成内容 Brief（Markdown 落盘 + 结构化返回）。"""
    brand = db.get(Brand, brand_id)
    if brand is None:
        return {"error": "brand 不存在"}

    vis = metrics.brand_visibility(db, brand_id)
    gaps = metrics.answer_gaps(db, brand_id)
    today = datetime.utcnow().date().isoformat()

    # 缺口主题清单（每主题一个内容建议）
    themes = []
    for g in gaps[:12]:
        themes.append({
            "query": g["query_text"],
            "engine": g.get("engine", ""),
            "competitors": g["competitors_present"],
            "snippet": g["snippet"][:100],
            "content_type": _scenario_type(g.get("scenario", "")),
            "faq_question": f"{g['query_text']}？",
        })

    # FAQ 候选（缺口问题直接转为 FAQ 条目）
    faqs = [{"question": f"{g['query_text']}？", "answer": "待撰写（参考 AI 现有回答 + 你的产品事实）"}
            for g in gaps[:10]]

    # 建议引用/参考信源：AI 当前最常引用的域名（内容布局的参照系）
    cited = vis.get("top_cited_domains", [])
    reference_sources = [{"domain": d["domain"], "count": d["count"]} for d in cited[:8]]

    brief = {
        "brand": brand.name,
        "date": today,
        "gaps_total": len(gaps),
        "visibility": vis.get("visibility_rate", 0),
        "themes": themes,
        "faqs": faqs,
        "reference_sources": reference_sources,
        "structure": structure_templates(brand),
        "authority": authority_score(db, brand_id),
        "index_checklist": INDEX_CHECKLIST,
    }

    # 落盘 Markdown
    md = _brief_to_markdown(brief)
    out_dir = os.path.join("reports", brand.name)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"内容优化Brief_{today}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(md)
    brief["path"] = path
    return brief


def _brief_to_markdown(b: dict) -> str:
    L = [f"# {b['brand']} · 内容优化 Brief（{b['date']}）", ""]
    L += [f"当前 AI 可见度 {b['visibility'] * 100:.1f}%，缺口 {b['gaps_total']} 个查询主题。",
          "", "## 1. 缺口主题 → 内容选题", "", "| 主题查询 | 引擎 | 竞争格局（谁在被引用） | 建议内容类型 |", "| --- | --- | --- | --- |"]
    if b["themes"]:
        for t in b["themes"]:
            comps = "、".join(t["competitors"][:3]) or "无直接竞品"
            L.append(f"| {t['query']} | {t['engine']} | {comps} | {t['content_type']} |")
    else:
        L.append("| （暂无缺口：竞品也没有出现在你的缺席位置，可先做品类词覆盖或新品主题） |")
    L += ["", "## 2. FAQ 候选（发布时做成 FAQPage Schema）", ""]
    for faq in b["faqs"][:10]:
        L.append(f"- Q：{faq['question']}")
        L.append(f"  - A：{faq['answer']}")
    L += ["", "## 3. AI 当前引用格局（内容布局参照系）", "",
          "AI 在回答里最常引用这些域名——它们是竞争内容，也是建议你的内容去被采信时需要超越的对象：", ""]
    L.append("| 域名 | 被引用次数 |")
    L.append("| --- | --- |")
    for s in b["reference_sources"]:
        L.append(f"| {s['domain']} | {s['count']} |")
    L += ["", "## 4. 结构化清单（发布前逐项打勾）", "", b["structure"]["checklist_md"],
          "", "### llms.txt 模板（放你官网根目录）", "", "```text", b["structure"]["llms_txt"], "```", "",
          "### FAQPage Schema 模板（JSON-LD，插入内容页 <head>）", "", "```json", b["structure"]["faq_schema_json"],
          "```", "", "## 5. 权威度建设", "", f"权威域引用：**{b['authority']['authority_citations']} / {b['authority']['total_citations']}**"
          f"（占比 {b['authority']['authority_ratio'] * 100:.1f}%）", "",
          "| 权威域 | 当前被引用 | 建议动作 |", "| --- | --- | --- |"]
    seen = set()
    for d in b["authority"]["cited_items"]:
        seen.add(d["domain"])
        L.append(f"| {d['domain']} | {d['count']} | 已进入 AI 引用链，做内容时参考其写法 |")
    for d in b["authority"]["targets"]:
        if d["domain"] not in seen:
            L.append(f"| {d['domain']} | 0 | {d['action']} |")
    L += ["", "## 6. 索引保障（发布后 48h 内检查）", ""]
    for c in b["index_checklist"]:
        L.append(f"- [ ] {c}")
    L += ["", "（本 Brief 由 GEO Studio 基于真实缺口/引用数据生成，动作清单可人工调整）", ""]
    return "\n".join(L)


# ---------- 2. 结构化 ----------

def structure_templates(brand: Brand) -> dict:
    """结构化三件套模板：llms.txt、FAQPage Schema、论证结构。"""
    llms_txt = f"""# {brand.name}
> {brand.name} 官网内容总览，供 AI 与搜索引擎索引。

## 品牌
- 简介：{brand.name} 的一句话介绍（替换为真实描述）
- 官网：https://{brand.official_domain or "example.com"}

## 核心页面
- 首页：https://{brand.official_domain or "example.com"}/
- 关于我们：https://{brand.official_domain or "example.com"}/about
- 产品/服务：https://{brand.official_domain or "example.com"}/products
- FAQ：https://{brand.official_domain or "example.com"}/faq

## 重点内容（发布后登记，用一句话概括内容，便于 AI 快速判断相关性）
- 文章：《标题》——一句话摘要
- 榜单：《标题》——一句话摘要
"""
    faq_schema = """{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "示例问题（替换为 Brief 第 2 节的 FAQ 候选）",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "示例回答：给出事实、数据、来源，50 字以上，让 AI 能直接摘取。"
      }
    }
  ]
}"""
    argument_structure = """发布前检查论证结构（让 AI 更容易摘取与引用）：
1. 开头 50 字内给出直接结论（AI 摘要通常只取前几句）；
2. 每个小节一个小标题，小标题本身就是一句完整结论；
3. 关键数据用 <table> 或列表呈现（结构化数据 AI 解析率最高）；
4. 至少 1 处引用可验证来源（官网/权威域链接）；
5. 全文覆盖用户真实问题（对照 Brief 的缺口主题），不绕弯。"""
    return {
        "llms_txt": llms_txt,
        "faq_schema_json": faq_schema,
        "argument_structure": argument_structure,
        "checklist_md": "\n".join([
            "- [ ] 官网根目录已放 llms.txt（AI 索引入口）",
            "- [ ] 内容页已插入 FAQPage JSON-LD Schema",
            "- [ ] 正文按“结论前置 + 小标题结论化 + 表格化数据”论证结构撰写",
            "- [ ] 页面已在 sitemap.xml 登记并提交",
        ]),
    }


# ---------- 3. 权威度建设 ----------

def authority_score(db: Session, brand_id: int) -> dict:
    """权威域引用统计：高权重域名（百科/行业站/内容平台）被 AI 引用的情况。"""
    brand = db.get(Brand, brand_id)
    if brand is None:
        return {"error": "brand 不存在"}
    vis = metrics.brand_visibility(db, brand_id)

    cited_items = []
    for d in vis.get("top_cited_domains", []):
        if _is_authority(d["domain"], brand):
            cited_items.append({"domain": d["domain"], "count": d["count"]})

    total = vis.get("total_citations", 0)
    authority_cited = sum(x["count"] for x in cited_items)

    # 建议动作清单（尚未被引用的权威域）
    cited_domains = {x["domain"] for x in cited_items}
    targets = []
    for a in AUTHORITY_DOMAINS:
        if a in cited_domains:
            continue
        action = "投稿/共建词条，让品牌进入该域的索引" if a in ("zh.wikipedia.org", "baike.baidu.com") else \
                 ("在平台发布官方账号内容，并挂官网链接" if a in ("zhihu.com", "xiaohongshu.com", "bilibili.com", "douyin.com", "mp.weixin.qq.com") else \
                  "联系编辑/发布新闻稿或白皮书，争取被引用")
        targets.append({"domain": a, "action": action})

    return {
        "authority_citations": authority_cited,
        "total_citations": total,
        "authority_ratio": (authority_cited / total) if total else 0,
        "cited_items": cited_items,
        "targets": targets,
    }


# ---------- 4. 索引保障 ----------

INDEX_CHECKLIST = [
    "新内容发布后提交 sitemap（Google Search Console / 百度站长平台）",
    "robots.txt 显式放行 AI 爬虫：GPTBot、ClaudeBot、Google-Extended、BaiduSpider、Bytespider",
    "内容 URL 保持稳定（不随意改链接），旧链接 301 到新地址",
    "对监控内容跑 check_index（python scripts/check_index.py <品牌id>），确认 AI 已收录",
]


def check_index(db: Session, brand_id: int, engine: str = "wenxin") -> dict:
    """索引保障：对品牌配置的 monitored_urls，直接问 AI"你是否了解这篇内容"，
    根据回答判断内容是否进入 AI 检索（RAG 收录）。返回逐条结果。"""
    brand = db.get(Brand, brand_id)
    if brand is None:
        return {"error": "brand 不存在"}
    monitored = [u.strip() for u in (brand.monitored_urls or []) if u and u.strip()]
    if not monitored:
        return {"error": "该品牌未配置 monitored_urls，无法检查索引"}

    from playwright.sync_api import sync_playwright
    from app.services import engines
    adapter = engines.get_adapter(engine)

    results = []
    with sync_playwright() as p:
        profile_dir = os.path.join("data", "browser_profile", engine)
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        try:
            for url in monitored:
                prompt = f"你了解这篇文章吗？它讲了什么主题？文章链接：{url}。如果没看过请直接说不知道。"
                try:
                    page = context.new_page()
                    text, _ = adapter.ask(page, prompt)
                    # 去掉页面回显的提示词与导航残渣，避免"不知道"来自提问词本身
                    clean = text.replace(prompt, "")
                    ui_marks = ("百度首页", "正在思考", "内容由AI生成", "相关搜索", "帮我写作", "PPT生成")
                    if len(clean) < 100 and any(m in clean for m in ui_marks):
                        results.append({"url": url, "indexed": None,
                                        "answer": "AI 未生成实质回答（可能排队/限流），建议错峰重试"})
                        continue
                    # 双向证据词：AI 明确说不知道 → 未收录；给出"了解/内容概述" → 已收录
                    not_known = any(k in clean for k in ("我不知道", "我没看过", "无法访问",
                                                         "没有相关信息", "并不了解", "我无法"))
                    knows = any(k in clean for k in ("了解", "这篇文章", "该页面", "主要内容",
                                                     "这是", "相关内容", "页面内容", "核心主题"))
                    if knows and not not_known and len(clean) > 100:
                        indexed = True
                    elif not_known:
                        indexed = False
                    else:
                        indexed = None  # 证据不足，需人工/重试
                    results.append({"url": url, "indexed": indexed, "answer": clean[:300]})
                except Exception as exc:
                    results.append({"url": url, "indexed": None, "answer": f"检查失败：{str(exc)[:200]}"})
        finally:
            context.close()
    return {"engine": engine, "results": results,
            "summary": {"indexed": sum(1 for r in results if r["indexed"]),
                        "not_indexed": sum(1 for r in results if r["indexed"] is False),
                        "failed": sum(1 for r in results if r["indexed"] is None)}}
