"""用真实品牌建演示：瑞幸咖啡（主品牌）+ 星巴克中国/库迪（竞品）。

创建品牌并自动展开：品牌词×场景（type=brand）+ 品类词×通用问题（type=category），
全部 4 个引擎建任务（wenxin 免登录可用，kimi/doubao/yuanbao 需登录后自动复用 cookie）。

用法：python scripts/seed_real_brand.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import Brand, Keyword, SamplingTask  # noqa: E402

DEFAULT_SCENARIOS = ["是什么", "怎么样", "值得推荐吗", "价格怎么样", "和竞品比怎么样"]
CATEGORY_SCENARIOS = [
    "有哪些{category}推荐", "什么{category}好", "{category}哪个牌子好",
    "{category}怎么选", "推荐一个{category}品牌", "买{category}要注意什么",
]
DEFAULT_ENGINES = ["wenxin", "kimi", "doubao", "yuanbao"]

BRAND_NAME = "瑞幸咖啡"
ALIASES = ["Luckin Coffee"]
CATEGORY = "咖啡"
OFFICIAL_DOMAIN = "luckincoffee.com"
MONITORED_URLS = [
    "https://www.luckincoffee.com/",
    "https://www.luckincoffee.com/about",
]
COMPETITORS = [
    {"name": "星巴克中国", "official_domain": "starbucks.com.cn"},
    {"name": "库迪咖啡", "official_domain": "cotti.cn"},
]


def main() -> None:
    db = SessionLocal()
    try:
        if db.query(Brand).filter(Brand.name == BRAND_NAME).first():
            print(f"品牌「{BRAND_NAME}」已存在，跳过")
            sys.exit(0)

        # 竞品
        comp_ids = []
        for c in COMPETITORS:
            comp = db.query(Brand).filter(Brand.name == c["name"]).first()
            if comp is None:
                comp = Brand(name=c["name"], industry="咖啡",
                             official_domain=c["official_domain"])
                db.add(comp)
                db.flush()
            comp_ids.append(comp.id)

        brand = Brand(
            name=BRAND_NAME,
            aliases=ALIASES,
            industry="咖啡",
            category=CATEGORY,
            official_domain=OFFICIAL_DOMAIN,
            competitor_ids=comp_ids,
            monitored_urls=MONITORED_URLS,
        )
        db.add(brand)
        db.flush()

        kw_count = 0
        task_count = 0
        query_names = [BRAND_NAME] + ALIASES
        for qn in query_names:
            for sc in DEFAULT_SCENARIOS:
                kw = Keyword(brand_id=brand.id, query_text=f"{qn} {sc}", scenario=sc, type="brand")
                db.add(kw)
                db.flush()
                for eng in DEFAULT_ENGINES:
                    db.add(SamplingTask(keyword_id=kw.id, engine=eng, frequency_hours=24))
                    task_count += 1
                kw_count += 1
        for tpl in CATEGORY_SCENARIOS:
            kw = Keyword(brand_id=brand.id, query_text=tpl.format(category=CATEGORY),
                         scenario="品类推荐", type="category")
            db.add(kw)
            db.flush()
            for eng in DEFAULT_ENGINES:
                db.add(SamplingTask(keyword_id=kw.id, engine=eng, frequency_hours=24))
                task_count += 1
            kw_count += 1

        db.commit()
        print(f"品牌「{BRAND_NAME}」（品类：{CATEGORY}，官网：{OFFICIAL_DOMAIN}）已创建")
        print(f"竞品：{', '.join(c['name'] for c in COMPETITORS)}（competitor_ids={comp_ids}）")
        print(f"关键词 {kw_count} 条，采样任务 {task_count} 条（引擎：{', '.join(DEFAULT_ENGINES)}）")
        print(f"内容监控 URL {len(MONITORED_URLS)} 条（官网页面，用于索引检查与引用追踪演示）")
    finally:
        db.close()


if __name__ == "__main__":
    main()
