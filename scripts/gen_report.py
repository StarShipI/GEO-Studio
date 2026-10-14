"""生成跨引擎对比 HTML 报告。

用法：python scripts/gen_report.py [brand_id]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.services.engine_report import generate_engine_report  # noqa: E402


def main() -> None:
    brand_id = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    db = SessionLocal()
    try:
        r = generate_engine_report(db, brand_id)
        print(r["path"])
    finally:
        db.close()


if __name__ == "__main__":
    main()
