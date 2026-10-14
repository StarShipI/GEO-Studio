"""数据库 v2 迁移：为已有库补加多引擎/Prompt 库完善所需的新列（幂等，可重复执行）。

新增列：
- keywords.type            brand=品牌词 | category=品类通用问题
- brands.category          品类词（商品/服务客户，如"咖啡"）
- brands.monitored_urls    自媒体客户要追踪的内容 URL（JSON）

用法：python scripts/migrate_v2.py
"""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import settings  # noqa: E402


def _db_path() -> str:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        return url[len("sqlite:///"):]
    raise SystemExit(f"只支持 SQLite 迁移，当前: {url}")


def main() -> None:
    path = _db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(path)
    cur = con.cursor()

    def add_col(table: str, col: str, ddl: str) -> bool:
        cols = {r[1] for r in cur.execute(f"PRAGMA table_info({table})")}
        if col in cols:
            return False
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}")
        return True

    changed = [
        add_col("keywords", "type", "VARCHAR(20) NOT NULL DEFAULT 'brand'"),
        add_col("brands", "category", "VARCHAR(50) NOT NULL DEFAULT ''"),
        add_col("brands", "monitored_urls", "JSON NOT NULL DEFAULT '[]'"),
    ]
    con.commit()
    print("迁移完成，新增列：", [c for c, ok in zip(
        ["keywords.type", "brands.category", "brands.monitored_urls"], changed) if ok] or "无（已是最新）")
    con.close()


if __name__ == "__main__":
    main()
