"""LLM 解析归因：把 AI 回答原文解析成 citations（引用）和 brand_mentions（提及）。

关键设计：
- 用 LLM + JSON 输出，不用正则硬啃（AI 回答格式千变万化）。
- LLM 只负责提取客观事实（链接、名字、语境），情感判断也交给它；
  brand_id 由本模块用「品牌名 / 别名 / 官方域名」本地匹配，保证主键可靠。
- 未配置 LLM API key 时跳过解析（采集仍可进行，数据后补）。
"""
from __future__ import annotations

import json
import logging
from urllib.parse import urlparse

from openai import OpenAI

from app.config import settings
from app.models import AIResponse, Brand, BrandMention, Citation

logger = logging.getLogger(__name__)

_PARSE_SYSTEM = (
    "你是 GEO（生成引擎优化）数据解析器。给你一段 AI 搜索引擎对用户问题的回答原文，"
    "请提取两类信息并只输出 JSON：\n"
    "1. citations：回答中出现的引用链接（网址），含 url（补全为以 http:// 或 https:// 开头）、"
    "position（该链接在回答中第一次出现的顺序，从 1 开始）、snippet（链接附近的一句话语境）；\n"
    "2. mentions：回答中出现的品牌/公司/产品实体提及，含 brand_name（实体的规范名）、"
    "sentiment（对该实体的态度，只能是 positive、negative 或 neutral）、"
    "context（提及处的一句话语境）。\n"
    "JSON 结构：{\"citations\": [...], \"mentions\": [...]}。没有则返回空数组，不要编造。"
)


def _norm_url(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    try:
        p = urlparse(raw)
        if p.netloc and "." in p.netloc:
            return raw
    except Exception:
        pass
    return None


def _domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _match_brand(db, name: str, url: str) -> int | None:
    """按名称/别名/官方域名把解析结果匹配到 brands 表，返回 brand_id。"""
    name = (name or "").strip().lower()
    url_domain = _domain_of(url or "")
    for b in db.query(Brand).all():
        names = {b.name.lower()} | {str(a).lower() for a in (b.aliases or [])}
        if name and name in names:
            return b.id
        if url_domain and b.official_domain:
            od = b.official_domain.lower().replace("https://", "").replace("http://", "")
            if url_domain == od or url_domain.endswith("." + od):
                return b.id
    return None


def parse_response(response_id: int, db=None) -> dict:
    """解析一条 AIResponse，写入 citations 与 brand_mentions。返回统计。"""
    from app.database import SessionLocal

    own_session = db is None
    db = db or SessionLocal()
    try:
        resp = db.get(AIResponse, response_id)
        if resp is None:
            return {"error": "response 不存在"}

        if not settings.llm_api_key:
            logger.warning("未配置 GEO_LLM_API_KEY，跳过解析 response#%s", response_id)
            return {"skipped": "no llm key"}

        client = OpenAI(base_url=settings.llm_api_base, api_key=settings.llm_api_key)
        completion = client.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _PARSE_SYSTEM},
                {"role": "user", "content": f"问题：{resp.prompt_text}\n\n回答原文：\n{resp.response_text}"},
            ],
        )
        content = completion.choices[0].message.content or "{}"
        data = json.loads(content)

        # 引用：去重 + 规范化 + 赋 position
        seen: set[str] = set()
        for i, cit in enumerate(data.get("citations") or [], start=1):
            url = _norm_url(str(cit.get("url", "")))
            if not url or url in seen:
                continue
            seen.add(url)
            db.add(Citation(
                response_id=response_id,
                url=url,
                domain=_domain_of(url),
                position=int(cit.get("position") or i),
                snippet=str(cit.get("snippet", ""))[:500],
            ))

        # 提及：本地匹配 brand_id
        mention_count = 0
        for men in data.get("mentions") or []:
            brand_name = str(men.get("brand_name", "")).strip()
            if not brand_name:
                continue
            url = _norm_url(str(men.get("url", "")))  # 若 LLM 附带链接则参与匹配
            sentiment = str(men.get("sentiment", "neutral"))
            if sentiment not in ("positive", "negative", "neutral"):
                sentiment = "neutral"
            db.add(BrandMention(
                response_id=response_id,
                brand_id=_match_brand(db, brand_name, url or ""),
                brand_name=brand_name[:100],
                sentiment=sentiment,
                context=str(men.get("context", ""))[:500],
            ))
            mention_count += 1

        db.commit()
        return {"citations": len(seen), "mentions": mention_count}
    except Exception as exc:
        logger.error("解析 response#%s 失败: %s", response_id, exc)
        return {"error": str(exc)}
    finally:
        if own_session:
            db.close()
