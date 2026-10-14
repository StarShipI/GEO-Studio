"""为演示品牌补全 v2 字段：category、monitored_urls、品类通用问题任务。

用法：python scripts/enrich_demo.py [brand_id]
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import Brand, Keyword, SamplingTask  # noqa: E402

CATEGORY_SCENARIOS = [
    "有哪些{category}推荐", "什么{category}好", "{category}哪个牌子好",
    "{category}怎么选", "推荐一个{category}品牌", "买{category}要注意什么",
]
DEMO_MONITORED_URLS = [
    "https://www.xiaohongshu.com/explore/demo-coffee-guide",
    "https://mp.weixin.qq.com/s/demo-coffee-ranking",
]


def main() -> None:
    brand_id = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    db = SessionLocal()
    try:
        brand = db.get(Brand, brand_id)
        if brand is None:
            print(f"品牌 {brand_id} 不存在")
            sys.exit(1)

        if not brand.category:
            brand.category = "咖啡"
        if not brand.monitored_urls:
            brand.monitored_urls = DEMO_MONITORED_URLS

        # 已存在的品类词不重复建
        existing_q = {k.query_text for k in db.query(Keyword).filter(Keyword.brand_id == brand_id)}
        created = 0
        for tpl in CATEGORY_SCENARIOS:
            q = tpl.format(category=brand.category)
            if q in existing_q:
                continue
            kw = Keyword(brand_id=brand_id, query_text=q, scenario="品类推荐", type="category")
            db.add(kw)
            db.flush()
            db.add(SamplingTask(keyword_id=kw.id, engine="wenxin", frequency_hours=24))
            created += 1
        db.commit()
        print(f"品牌「{brand.name}」category={brand.category}，monitored_urls={len(brand.monitored_urls)} 条，"
              f"新建品类任务 {created} 条")
    finally:
        db.close()


if __name__ == "__main__":
    main()
