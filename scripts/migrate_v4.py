# -*- coding: utf-8 -*-
"""v4 迁移：content_items 表（账号 GEO 内容清单）。

Base.metadata.create_all 建新表；再从各品牌的 monitored_urls 幂等回填内容，
平台按域名自动识别。
"""
import sys
sys.path.insert(0, ".")

from app.database import Base, SessionLocal, engine
from app.models import Brand
from app.services import account

Base.metadata.create_all(engine)
print("tables:", sorted(Base.metadata.tables.keys()))

db = SessionLocal()
try:
    brands = db.query(Brand).all()
    for b in brands:
        before = len(db.query(account.ContentItem).filter(account.ContentItem.brand_id == b.id).all()) if hasattr(account, "ContentItem") else 0
        account.sync_content_items(db, b.id)
        after = len(db.query(account.ContentItem).filter(account.ContentItem.brand_id == b.id).all())
        print(f"brand#{b.id} {b.name}: content_items {before} -> {after}")
finally:
    db.close()
print("v4 done")
