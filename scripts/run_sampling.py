"""手动触发采样（直接调服务层，不走 HTTP，方便调试）。

用法（项目根目录）：
    python scripts/run_sampling.py            # 所有到期任务（含 error 重试）
    python scripts/run_sampling.py 2          # 指定品牌 id
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.scraper import scraper_service  # noqa: E402


def main() -> None:
    if len(sys.argv) > 1:
        brand_id = int(sys.argv[1])
        print(f"触发品牌 {brand_id} 的全部任务…")
        result = scraper_service.run_brand(brand_id)
    else:
        print("触发所有到期任务…")
        result = scraper_service.run_due_tasks()
    if not result:
        print("没有可执行的任务（都还没到期？）")
    for task_id, msg in result.items():
        print(f"  任务 {task_id}: {msg}")


if __name__ == "__main__":
    main()
