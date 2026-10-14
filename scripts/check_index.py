"""索引保障检查：对品牌配置的 monitored_urls 内容，问 AI 引擎验证是否已收录。

用法：python scripts/check_index.py [brand_id] [engine]
默认引擎 wenxin（免登录可用）。
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.services.content import check_index  # noqa: E402


def main() -> None:
    brand_id = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    engine = sys.argv[2] if len(sys.argv) > 2 else "wenxin"
    db = SessionLocal()
    try:
        r = check_index(db, brand_id, engine=engine)
        if "error" in r:
            print(r["error"])
            sys.exit(1)
        s = r["summary"]
        print(f"索引检查（引擎 {r['engine']}）：已收录 {s['indexed']} / 未收录 {s['not_indexed']} / 失败 {s['failed']}")
        for item in r["results"]:
            tag = {True: "已收录", False: "未收录", None: "失败"}[item["indexed"]]
            print(f"\n[{tag}] {item['url']}")
            print(f"   AI 回答：{item['answer'][:200]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
