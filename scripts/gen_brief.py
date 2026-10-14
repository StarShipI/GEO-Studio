"""生成内容优化 Brief（AI-ready 内容生成 + 结构化模板 + 权威度 + 索引保障）。

用法：python scripts/gen_brief.py [brand_id]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.services.content import generate_brief  # noqa: E402


def main() -> None:
    brand_id = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    db = SessionLocal()
    try:
        r = generate_brief(db, brand_id)
        if "error" in r:
            print(r["error"])
            sys.exit(1)
        print(f"Brief 已生成：{r['path']}")
        print(f"  缺口主题 {len(r['themes'])} 个，FAQ 候选 {len(r['faqs'])} 条")
        print(f"  权威域引用 {r['authority']['authority_citations']}/{r['authority']['total_citations']}"
              f"（{r['authority']['authority_ratio'] * 100:.1f}%）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
