"""运行级验证：表结构、演示数据、指标函数、周报生成链路。

用法：python scripts/verify.py
"""
from __future__ import annotations

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Brand, Keyword, SamplingTask  # noqa: E402
from app.services import metrics, reporter  # noqa: E402

EXPECTED_TABLES = {
    "alerts", "ai_responses", "brand_mentions", "brands",
    "citations", "keywords", "reports", "sampling_tasks",
}


def main() -> None:
    ok = True

    # 1. 表结构
    con = sqlite3.connect("data/geo.db")
    tables = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
    missing = EXPECTED_TABLES - tables
    print(f"[1] 表结构：共 {len(tables)} 张，缺失 {missing or '无'}")
    ok = ok and not missing
    con.close()

    # 2. 应用导入
    print(f"[2] FastAPI 应用导入 OK，路由数 {len(app.routes)}")

    # 3. 演示数据
    db = SessionLocal()
    brand = db.query(Brand).filter(Brand.name == "澄心咖啡").first()
    kw_count = db.query(Keyword).filter(Keyword.brand_id == brand.id).count()
    task_count = db.query(SamplingTask).filter(SamplingTask.status == "active").count()
    print(f"[3] 演示品牌 {brand.name}，关键词 {kw_count} 条，启用任务 {task_count} 条")
    ok = ok and brand and kw_count > 0 and task_count > 0

    # 4. 指标函数（空数据场景，应正常返回不报错）
    vis = metrics.brand_visibility(db, brand.id)
    gaps = metrics.answer_gaps(db, brand.id)
    print(f"[4] 可见度指标 {vis['visibility_rate']}，缺口 {len(gaps)} 条（空数据正常）")

    # 5. 周报生成链路（含落盘）
    rep = reporter.generate_weekly_report(db, brand.id, days=7)
    path = rep["path"]
    print(f"[5] 周报生成 OK：report_id={rep['report_id']}，文件 {path}")
    ok = ok and os.path.exists(path)
    db.close()

    print("\n验证结果：", "全部通过" if ok else "存在问题，请查看上方输出")


if __name__ == "__main__":
    main()
