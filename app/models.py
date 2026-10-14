"""8 张核心表的 ORM 模型。

设计要点：
- ai_responses 存 AI 回答原文快照（可回溯，客户质疑时能翻出"AI 当时怎么说的"）。
- citations / brand_mentions 都挂在 response_id 上，保证"一个回答只解析一次、指标可由明细重算"。
"""
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Brand(Base):
    """客户品牌（一个客户品牌一条记录）。"""
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)          # 品牌别名，如 ["豆包", "doubao"]
    industry: Mapped[str] = mapped_column(String(50), default="")
    category: Mapped[str] = mapped_column(String(50), default="")      # 品类词（商品/服务客户），如"咖啡"
    official_domain: Mapped[str] = mapped_column(String(200), default="")  # 官网域名，如 example.com
    competitor_ids: Mapped[list] = mapped_column(JSON, default=list)    # 竞品 brands.id 列表
    monitored_urls: Mapped[list] = mapped_column(JSON, default=list)    # 自媒体客户要追踪的内容 URL（RAG 引用监控）
    alert_negative_threshold: Mapped[int] = mapped_column(Integer, default=1)    # 负面提及告警阈值（条）
    alert_visibility_drop: Mapped[float] = mapped_column(default=0.2)           # 可见度下降告警阈值（百分点，如 0.2=20%）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Keyword(Base):
    """查询词：品牌词×场景词 与 品类词×通用问题 展开后的结果。"""
    __tablename__ = "keywords"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    query_text: Mapped[str] = mapped_column(Text)
    scenario: Mapped[str] = mapped_column(String(50), default="")      # 场景标签：是什么/怎么样/对比...
    type: Mapped[str] = mapped_column(String(20), default="brand")     # brand=品牌词 | category=品类通用问题
    priority: Mapped[int] = mapped_column(Integer, default=1)


class SamplingTask(Base):
    """采样任务：哪个引擎、多久问一次这个 query。"""
    __tablename__ = "sampling_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    keyword_id: Mapped[int] = mapped_column(ForeignKey("keywords.id"), index=True)
    engine: Mapped[str] = mapped_column(String(30), default="kimi")    # 引擎适配器名，见 services/engines.py
    frequency_hours: Mapped[int] = mapped_column(Integer, default=24)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | paused | error
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class AIResponse(Base):
    """AI 回答原文快照（证据层，最重要的一张表）。"""
    __tablename__ = "ai_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("sampling_tasks.id"), index=True)
    engine: Mapped[str] = mapped_column(String(30), default="")
    model: Mapped[str] = mapped_column(String(60), default="")
    prompt_text: Mapped[str] = mapped_column(Text)
    response_text: Mapped[str] = mapped_column(Text)
    sampled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class Citation(Base):
    """URL 级引用归因：AI 回答里引用了哪个链接、出现在第几个位置。"""
    __tablename__ = "citations"

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("ai_responses.id"), index=True)
    url: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)          # 在回答中出现的顺序
    snippet: Mapped[str] = mapped_column(Text, default="")


class BrandMention(Base):
    """品牌提及：谁在回答里被提了、什么情感、什么语境。"""
    __tablename__ = "brand_mentions"

    id: Mapped[int] = mapped_column(primary_key=True)
    response_id: Mapped[int] = mapped_column(ForeignKey("ai_responses.id"), index=True)
    brand_id: Mapped[int | None] = mapped_column(ForeignKey("brands.id"), nullable=True, index=True)
    brand_name: Mapped[str] = mapped_column(String(100), index=True)   # LLM 解析出的名字
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral")  # positive | negative | neutral
    context: Mapped[str] = mapped_column(Text, default="")             # 提及所在的语境片段


class Report(Base):
    """周期报告（周报）。metrics_json 存指标快照，content_md 存 Markdown 正文。"""
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime)
    period_end: Mapped[datetime] = mapped_column(DateTime)
    metrics_json: Mapped[dict] = mapped_column(JSON, default=dict)
    content_md: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Alert(Base):
    """告警：负面提及 / 可见度骤降 / 答案缺口。"""
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    type: Mapped[str] = mapped_column(String(30))          # negative_mention | visibility_drop | gap
    severity: Mapped[str] = mapped_column(String(10), default="medium")  # low | medium | high
    detail: Mapped[str] = mapped_column(Text, default="")
    is_resolved: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ContentItem(Base):
    """自媒体账号监控的内容单元（一篇文章/一篇笔记/一个视频页）。

    由 brands.monitored_urls 派生（读取时幂等同步），额外承载平台与发布时间，
    支撑：内容级 RAG 归因、收录时效（发布时间→首次被引用）、跨平台发布效果归因。
    """
    __tablename__ = "content_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    url: Mapped[str] = mapped_column(Text, index=True)
    platform: Mapped[str] = mapped_column(String(50), default="")        # 小红书/公众号/知乎/B站/抖音/微博/官网/其他
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 内容发布时间（收录时效基准）
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Snapshot(Base):
    """可见度历史快照：每轮采样完成后为品牌写一行，支撑趋势/环比。

    engine 为空表示全引擎汇总行；有值表示该引擎单独一行。
    """
    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True)
    engine: Mapped[str] = mapped_column(String(30), default="")       # "" = 全引擎汇总
    total_queries: Mapped[int] = mapped_column(Integer, default=0)
    mentioned_queries: Mapped[int] = mapped_column(Integer, default=0)
    visibility_rate: Mapped[float] = mapped_column(default=0.0)
    total_citations: Mapped[int] = mapped_column(Integer, default=0)
    own_citations: Mapped[int] = mapped_column(Integer, default=0)
    sov: Mapped[float | None] = mapped_column(nullable=True)         # None=样本不足
    negative_mentions: Mapped[int] = mapped_column(Integer, default=0)
    sampled_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
