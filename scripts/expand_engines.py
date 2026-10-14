"""为现有品牌补齐缺失引擎的采样任务（新增引擎后一键扩展，无需重建品牌）。

用法（项目根目录）：
    python scripts/expand_engines.py              # 补齐到全部已注册引擎
    python scripts/expand_engines.py yuanbao      # 只补指定引擎
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import Keyword, SamplingTask  # noqa: E402
from app.services import engines  # noqa: E402


def main() -> None:
    targets = sys.argv[1:] or list(engines.REGISTRY)
    for eng in targets:
        if eng not in engines.REGISTRY:
            print(f"未知引擎 {eng}，可用: {list(engines.REGISTRY)}")
            sys.exit(1)

    db = SessionLocal()
    try:
        created = 0
        for kw in db.query(Keyword).all():
            existing = {
                t.engine for t in db.query(SamplingTask)
                .filter(SamplingTask.keyword_id == kw.id).all()
            }
            for eng in targets:
                if eng not in existing:
                    db.add(SamplingTask(keyword_id=kw.id, engine=eng, frequency_hours=24))
                    created += 1
        db.commit()
        print(f"已补齐 {len(targets)} 个引擎的任务，共新建 {created} 条采样任务")
    finally:
        db.close()


if __name__ == "__main__":
    main()
