"""初始化数据库，可选插入演示数据。

用法（在项目根目录 geo-studio/ 下执行）：
    python scripts/init_db.py            # 只建表
    python scripts/init_db.py --seed     # 建表 + 演示品牌「澄心咖啡」及其采样任务
"""
from __future__ import annotations

import argparse
import os
import sys

# 保证能从项目根目录导入 app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal, init_db  # noqa: E402
from app.models import Brand, Keyword, SamplingTask  # noqa: E402

DEMO_SCENARIOS = ["是什么", "怎么样", "值得推荐吗", "价格怎么样", "和竞品比怎么样"]
DEMO_CATEGORY_SCENARIOS = [
    "有哪些{category}推荐", "什么{category}好", "{category}哪个牌子好",
    "{category}怎么选", "推荐一个{category}品牌", "买{category}要注意什么",
]
# 演示用内容监控 URL（自媒体/RAG 引用追踪）
DEMO_MONITORED_URLS = [
    "https://www.xiaohongshu.com/explore/demo-coffee-guide",   # 演示 URL，替换为客户真实发布链接
    "https://mp.weixin.qq.com/s/demo-coffee-ranking",
]


def seed_demo() -> None:
    db = SessionLocal()
    try:
        if db.query(Brand).filter(Brand.name == "澄心咖啡").first():
            print("演示品牌已存在，跳过")
            return

        comp = Brand(name="山丘咖啡", aliases=["山丘"], industry="咖啡",
                     official_domain="hillcoffee.com")
        db.add(comp)
        db.flush()

        brand = Brand(name="澄心咖啡", aliases=["澄心", "CX Coffee"], industry="咖啡",
                      category="咖啡", official_domain="chengxin-coffee.com",
                      competitor_ids=[comp.id], monitored_urls=DEMO_MONITORED_URLS)
        db.add(brand)
        db.flush()

        created = 0
        for sc in DEMO_SCENARIOS:
            kw = Keyword(brand_id=brand.id, query_text=f"澄心咖啡 {sc}", scenario=sc, type="brand")
            db.add(kw)
            db.flush()
            db.add(SamplingTask(keyword_id=kw.id, engine="wenxin", frequency_hours=24))
            created += 1
        for tpl in DEMO_CATEGORY_SCENARIOS:
            kw = Keyword(brand_id=brand.id, query_text=tpl.format(category=brand.category),
                         scenario="品类推荐", type="category")
            db.add(kw)
            db.flush()
            db.add(SamplingTask(keyword_id=kw.id, engine="wenxin", frequency_hours=24))
            created += 1
        db.commit()
        print(f"演示数据已就绪：品牌「澄心咖啡」（品类：咖啡）+ 竞品「山丘咖啡」，"
              f"共 {created} 个采样任务（引擎 wenxin，每日重采）")
        print(f"已配置 {len(DEMO_MONITORED_URLS)} 条内容监控 URL（演示用，记得换成真实链接）")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="GEO Studio 数据库初始化")
    parser.add_argument("--seed", action="store_true", help="同时插入演示数据")
    args = parser.parse_args()

    init_db()
    print("数据库初始化完成")
    if args.seed:
        seed_demo()


if __name__ == "__main__":
    main()
