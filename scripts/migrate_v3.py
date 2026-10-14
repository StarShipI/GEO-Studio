# -*- coding: utf-8 -*-
"""v3 迁移（幂等）：
- brands 表加告警配置列：alert_negative_threshold / alert_visibility_drop
- 新建 snapshots 表（可见度历史快照，趋势/环比用）
"""
import sqlite3, os

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "geo.db")

conn = sqlite3.connect(DB, timeout=30)
cur = conn.cursor()

# brands 加列（幂等）
cur.execute("PRAGMA table_info(brands)")
cols = {r[1] for r in cur.fetchall()}
if "alert_negative_threshold" not in cols:
    cur.execute("ALTER TABLE brands ADD COLUMN alert_negative_threshold INTEGER DEFAULT 1")
    print("brands +alert_negative_threshold")
if "alert_visibility_drop" not in cols:
    cur.execute("ALTER TABLE brands ADD COLUMN alert_visibility_drop REAL DEFAULT 0.2")
    print("brands +alert_visibility_drop")

# snapshots 表（幂等）
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='snapshots'")
if not cur.fetchone():
    cur.execute("""
        CREATE TABLE snapshots (
            id INTEGER PRIMARY KEY,
            brand_id INTEGER NOT NULL REFERENCES brands(id),
            engine VARCHAR(30) DEFAULT '',
            total_queries INTEGER DEFAULT 0,
            mentioned_queries INTEGER DEFAULT 0,
            visibility_rate REAL DEFAULT 0.0,
            total_citations INTEGER DEFAULT 0,
            own_citations INTEGER DEFAULT 0,
            sov REAL,
            negative_mentions INTEGER DEFAULT 0,
            sampled_at DATETIME
        )
    """)
    cur.execute("CREATE INDEX ix_snapshots_brand_id ON snapshots(brand_id)")
    cur.execute("CREATE INDEX ix_snapshots_sampled_at ON snapshots(sampled_at)")
    print("snapshots 表已创建")

conn.commit()
cur.execute("SELECT count(*) FROM snapshots")
print("snapshots 现有行数:", cur.fetchone()[0])
conn.close()
print("v3 迁移完成")
