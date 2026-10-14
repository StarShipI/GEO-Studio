-- GEO 服务型 MVP 独立建表 SQL（与 app/models.py 的 ORM 等价，可用任意 SQLite 工具执行）
-- 直接执行：sqlite3 data/geo.db < sql/schema.sql

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    aliases JSON NOT NULL DEFAULT '[]',
    industry VARCHAR(50) NOT NULL DEFAULT '',
    category VARCHAR(50) NOT NULL DEFAULT '',             -- v2：品类词（商品/服务客户），如"咖啡"
    official_domain VARCHAR(200) NOT NULL DEFAULT '',
    competitor_ids JSON NOT NULL DEFAULT '[]',
    monitored_urls JSON NOT NULL DEFAULT '[]',            -- v2：自媒体内容监控 URL（RAG 引用追踪）
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_brands_name ON brands (name);

CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER NOT NULL REFERENCES brands (id),
    query_text TEXT NOT NULL,
    scenario VARCHAR(50) NOT NULL DEFAULT '',
    type VARCHAR(20) NOT NULL DEFAULT 'brand',            -- v2：brand=品牌词 | category=品类通用问题
    priority INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS ix_keywords_brand_id ON keywords (brand_id);

CREATE TABLE IF NOT EXISTS sampling_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword_id INTEGER NOT NULL REFERENCES keywords (id),
    engine VARCHAR(30) NOT NULL DEFAULT 'kimi',
    frequency_hours INTEGER NOT NULL DEFAULT 24,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    last_run_at DATETIME,
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS ix_sampling_tasks_keyword_id ON sampling_tasks (keyword_id);

CREATE TABLE IF NOT EXISTS ai_responses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL REFERENCES sampling_tasks (id),
    engine VARCHAR(30) NOT NULL DEFAULT '',
    model VARCHAR(60) NOT NULL DEFAULT '',
    prompt_text TEXT NOT NULL,
    response_text TEXT NOT NULL,
    sampled_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_ai_responses_task_id ON ai_responses (task_id);
CREATE INDEX IF NOT EXISTS ix_ai_responses_sampled_at ON ai_responses (sampled_at);

CREATE TABLE IF NOT EXISTS citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES ai_responses (id),
    url TEXT NOT NULL,
    domain VARCHAR(255) NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    snippet TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_citations_response_id ON citations (response_id);
CREATE INDEX IF NOT EXISTS ix_citations_domain ON citations (domain);

CREATE TABLE IF NOT EXISTS brand_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    response_id INTEGER NOT NULL REFERENCES ai_responses (id),
    brand_id INTEGER REFERENCES brands (id),
    brand_name VARCHAR(100) NOT NULL,
    sentiment VARCHAR(20) NOT NULL DEFAULT 'neutral',
    context TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_brand_mentions_response_id ON brand_mentions (response_id);
CREATE INDEX IF NOT EXISTS ix_brand_mentions_brand_id ON brand_mentions (brand_id);
CREATE INDEX IF NOT EXISTS ix_brand_mentions_brand_name ON brand_mentions (brand_name);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER NOT NULL REFERENCES brands (id),
    period_start DATETIME NOT NULL,
    period_end DATETIME NOT NULL,
    metrics_json JSON NOT NULL DEFAULT '{}',
    content_md TEXT NOT NULL DEFAULT '',
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_reports_brand_id ON reports (brand_id);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER NOT NULL REFERENCES brands (id),
    type VARCHAR(30) NOT NULL,
    severity VARCHAR(10) NOT NULL DEFAULT 'medium',
    detail TEXT NOT NULL DEFAULT '',
    is_resolved BOOLEAN NOT NULL DEFAULT 0,
    created_at DATETIME NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_alerts_brand_id ON alerts (brand_id);
