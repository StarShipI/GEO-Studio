"""把某品牌的采样任务引擎切换到指定引擎（用于 Kimi 限流时换豆包等）。

用法（项目根目录）：
    python scripts/set_engine.py doubao 2        # 品牌 2 全部任务改用豆包
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import Keyword, SamplingTask  # noqa: E402
from app.services import engines  # noqa: E402


def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python scripts/set_engine.py <引擎名> <品牌id>")
        sys.exit(1)
    engine, brand_id = sys.argv[1], int(sys.argv[2])
    if engine not in engines.REGISTRY:
        print(f"未知引擎 {engine}，可用: {list(engines.REGISTRY)}")
        sys.exit(1)

    db = SessionLocal()
    try:
        tasks = (
            db.query(SamplingTask)
            .join(Keyword, SamplingTask.keyword_id == Keyword.id)
            .filter(Keyword.brand_id == brand_id)
            .all()
        )
        for t in tasks:
            t.engine = engine
            t.status = "error"   # 强制为 error，下次触发即重跑
            t.last_error = f"engine 已切换到 {engine}"
        db.commit()
        print(f"品牌 {brand_id} 的 {len(tasks)} 个任务已切换到引擎 {engine}（下次采样自动重跑）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
